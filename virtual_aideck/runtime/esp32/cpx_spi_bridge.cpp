#include "dpi/models.hpp"

#include "cpx_protocol.hpp"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <deque>
#include <string>
#include <vector>
#ifdef STRICT_EDGE_AUDIT
#include "edge_audit.hpp"
#endif

class CpxSpiBridge;

class BridgeQspi : public Qspi_itf {
 public:
  explicit BridgeQspi(CpxSpiBridge *top) : top_(top) {}
  void edge(int64_t timestamp, int data_0, int data_1, int data_2,
            int data_3, int mask) override;
  void cs_edge(int64_t timestamp, int cs) override;

 private:
  CpxSpiBridge *top_;
};

class BridgeNotifyGpio : public Gpio_itf {
 public:
  explicit BridgeNotifyGpio(CpxSpiBridge *top) : top_(top) {}
  void edge(int64_t timestamp, int data) override;

 private:
  CpxSpiBridge *top_;
};

class CpxSpiBridge : public Dpi_model {
  friend class BridgeQspi;
  friend class BridgeNotifyGpio;

 public:
  CpxSpiBridge(js::config *config, void *handle)
      : Dpi_model(config, handle),
        qspi_(new BridgeQspi(this)),
        notify_(new BridgeNotifyGpio(this)),
        ready_(new Gpio_itf()),
        port_(config->get("port") == nullptr ? 5000
                                               : config->get("port")->get_int()),
        packet_log_(config->get("packet_log") == nullptr
                        ? true
                        : config->get("packet_log")->get_int() != 0),
        network_poll_ps_(config->get("network_poll_ps") == nullptr
                             ? 100000
                             : config->get("network_poll_ps")->get_int()),
        queue_capacity_(config->get("queue_capacity") == nullptr
                            ? 10U
                            : static_cast<unsigned>(config->get("queue_capacity")->get_int())),
        current_cs_(1),
        notify_level_(0),
        handshake_armed_(false),
        ready_pending_(false),
        transaction_handshake_(false),
        pending_bits_(0),
        pending_byte_(0),
        listen_fd_(-1),
        client_fd_(-1),
        tx_offset_(0),
        transactions_(0),
        routed_(0),
        sent_(0),
        backpressure_events_(0),
        max_queue_depth_(0) {
    create_itf("input", static_cast<Dpi_itf *>(qspi_));
    create_itf("gpio_notify", static_cast<Dpi_itf *>(notify_));
    create_itf("gpio_ready", static_cast<Dpi_itf *>(ready_));
    trace_ = trace_new("cpx_spi_bridge");
    print("VESP32_INIT port=%d SPI=1/CS0 mode=0 GAP_RTT=A3 ESP_RTT=A18\n",
          port_);
  }

  void start() override {
    ready_->set_data(0);
    if (open_server()) {
      create_periodic_handler(network_poll_ps_, (void *)&CpxSpiBridge::network_poll_stub,
                              this);
    }
  }

  void stop() override {
    std::fprintf(stderr,
                 "VESP32_SUMMARY transactions=%u routed=%u sent=%u "
                 "backpressure=%u max_queue=%u queued=%u\n",
                 transactions_, routed_, sent_, backpressure_events_,
                 max_queue_depth_, static_cast<unsigned>(tx_queue_.size()));
    std::fflush(stderr);
    close_socket(&listen_fd_);
    close_socket(&client_fd_);
  }

 private:
  static void close_socket(int *fd) {
    if (*fd >= 0) {
      shutdown(*fd, SHUT_RDWR);
      close(*fd);
      *fd = -1;
    }
  }

  void notify_edge(int64_t timestamp, int data) {
    (void)timestamp;
    const int previous = notify_level_;
    notify_level_ = data != 0;
    if (!previous && notify_level_) {
      // A stalled host must not kill the camera firmware's ready timeout.
      // Disconnect explicitly; next client starts at a complete metadata envelope.
      if (tx_queue_.size() >= queue_capacity_) disconnect_client("slow_client_queue_limit");
      if (tx_queue_.size() >= queue_capacity_) {
        ready_pending_ = true;
        ++backpressure_events_;
        std::fprintf(stderr,
                     "VESP32_BACKPRESSURE ASSERT queue=%u capacity=%u\n",
                     static_cast<unsigned>(tx_queue_.size()), queue_capacity_);
        std::fflush(stderr);
      } else {
        assert_ready();
      }
    } else if (previous && !notify_level_) {
      ready_pending_ = false;
    }
  }

  void assert_ready() {
#ifdef STRICT_EDGE_AUDIT
    strict_audit::event(4, 0, 1); // Ordered output value; input timestamp captured at notify.
#endif
    handshake_armed_ = true;
    ready_pending_ = false;
    ready_->set_data(1);
    if (packet_log_) {
      std::fprintf(stderr, "VESP32_HANDSHAKE GAP_RTT_RISE ESP_RTT_HIGH\n");
      std::fflush(stderr);
    }
  }

  void cs_edge(int64_t timestamp, int cs) {
    (void)timestamp;
    if (cs == current_cs_) {
      return;
    }
    current_cs_ = cs;
    if (cs == 0) {
      transaction_.clear();
      pending_bits_ = 0;
      pending_byte_ = 0;
      transaction_handshake_ =
          handshake_armed_ && notify_level_ && current_ready_level();
      qspi_->set_data(0);
      if (!transaction_handshake_) {
        std::fprintf(stderr,
                     "VESP32_REJECT SPI_CS_WITHOUT_READY_HANDSHAKE\n");
        std::fflush(stderr);
      }
      return;
    }

    ready_->set_data(0);
    handshake_armed_ = false;
#ifdef STRICT_EDGE_AUDIT
    strict_audit::event(4, timestamp, 0);
    strict_audit::report();
#endif
    if (pending_bits_ != 0) {
      std::fprintf(stderr,
                   "VESP32_REJECT NON_BYTE_ALIGNED_SPI_TRANSFER bits=%d\n",
                   pending_bits_);
      std::fflush(stderr);
      return;
    }
    if (!transaction_handshake_) {
      return;
    }
    if (notify_level_ != 0) {
      std::fprintf(stderr,
                   "VESP32_REJECT GAP_RTT_NOT_LOW_BEFORE_TRANSFER_END\n");
      std::fflush(stderr);
      return;
    }
    if (packet_log_) {
      std::fprintf(stderr,
                   "VESP32_HANDSHAKE COMPLETE bytes=%u GAP_RTT=%d ESP_RTT_LOW\n",
                   static_cast<unsigned>(transaction_.size()), notify_level_);
      std::fflush(stderr);
    }
    ++transactions_;
    route_transaction();
  }

  bool current_ready_level() const {
    // The model owns this output and only deasserts it at transaction end.
    return handshake_armed_;
  }

  void spi_bit(int data_0) {
    if (current_cs_ != 0) {
      return;
    }
    pending_byte_ = static_cast<uint8_t>((pending_byte_ << 1) | (data_0 & 1));
    ++pending_bits_;
    if (pending_bits_ == 8) {
      if (transaction_.size() < 2048) {
        transaction_.push_back(pending_byte_);
      }
      pending_bits_ = 0;
      pending_byte_ = 0;
    }
    qspi_->set_data(0);
  }

  void route_transaction() {
    cpx::DecodedFrame decoded;
    std::string error;
    if (!cpx::decode_gap8_to_host(transaction_.data(), transaction_.size(),
                                  &decoded, &error)) {
      std::fprintf(stderr, "VESP32_CPX_REJECT %s\n", error.c_str());
      std::fflush(stderr);
      return;
    }

    if (client_fd_ < 0) { ++unconnected_packets_; return; }
    if (!frame_synced_) {
      const auto &w = decoded.wire_frame;
      if (w.size()!=48 || w[4]!=0xbd || w[5]!=2 || w[6]!=1) return;
      frame_synced_=true;
      std::fprintf(stderr,"RUNTIME_TCP_FRAME_SYNC unconnected_packets=%llu\n",
                   (unsigned long long)unconnected_packets_);
    }
    if (tx_queue_.size() >= queue_capacity_) {
      std::fprintf(stderr, "VESP32_TCP_QUEUE_FULL packet rejected\n");
      std::fflush(stderr);
      return;
    }
    tx_queue_.push_back(decoded.wire_frame);
    ++routed_;
    if (tx_queue_.size() > max_queue_depth_) {
      max_queue_depth_ = static_cast<unsigned>(tx_queue_.size());
    }
    if (packet_log_) {
      std::fprintf(stderr,
                   "VESP32_CPX_ROUTE_ACCEPT src=%u dst=%u function=%u version=%u "
                   "last=%u wire_bytes=%u queue_depth=%u\n",
                   decoded.route.source, decoded.route.destination,
                   decoded.route.function, decoded.route.version,
                   decoded.route.last_packet ? 1 : 0,
                   static_cast<unsigned>(decoded.wire_frame.size()),
                   static_cast<unsigned>(tx_queue_.size()));
      std::fflush(stderr);
    }
  }

  bool open_server() {
    listen_fd_ = socket(AF_INET, SOCK_STREAM, 0);
    if (listen_fd_ < 0) {
      std::fprintf(stderr, "VESP32_TCP_ERROR socket: %s\n", std::strerror(errno));
      return false;
    }
    int one = 1;
    setsockopt(listen_fd_, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    sockaddr_in address;
    std::memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = htons(static_cast<uint16_t>(port_));
    if (bind(listen_fd_, reinterpret_cast<sockaddr *>(&address),
             sizeof(address)) < 0 ||
        listen(listen_fd_, 1) < 0) {
      std::fprintf(stderr, "VESP32_TCP_ERROR bind/listen port %d: %s\n", port_,
                   std::strerror(errno));
      close_socket(&listen_fd_);
      return false;
    }
    const int flags = fcntl(listen_fd_, F_GETFL, 0);
    fcntl(listen_fd_, F_SETFL, flags | O_NONBLOCK);
    std::fprintf(stderr, "VESP32_TCP_LISTEN 127.0.0.1:%d\n", port_);
    std::fflush(stderr);
    return true;
  }

  bool accept_client() {
    client_fd_ = accept(listen_fd_, nullptr, nullptr);
    if (client_fd_ < 0) {
      if (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) {
        std::fprintf(stderr, "VESP32_TCP_ERROR accept: %s\n",
                     std::strerror(errno));
      }
      return false;
    }
    const int flags = fcntl(client_fd_, F_GETFL, 0);
    fcntl(client_fd_, F_SETFL, flags | O_NONBLOCK);
    frame_synced_=false;
    tx_queue_.clear(); tx_offset_=0;
    std::fprintf(stderr, "VESP32_TCP_CLIENT_CONNECTED\n");
    std::fflush(stderr);
    return true;
  }

  static void network_poll_stub(CpxSpiBridge *bridge) {
    bridge->network_poll();
  }

  void network_poll() {
    if ((++poll_counter_ & 65535U)==0 && client_fd_>=0) {
      char byte;
      ssize_t n=recv(client_fd_,&byte,1,MSG_PEEK|MSG_DONTWAIT);
      if (n==0 || n>0 || (n<0 && errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR))
        disconnect_client(n>0 ? "read_only_endpoint" : "peer_closed");
    }
    if (client_fd_ < 0) {
      if ((poll_counter_ & 65535U)==0) accept_client();
      return;
    }
    if (tx_queue_.empty()) {
      return;
    }
    const std::vector<uint8_t> &frame = tx_queue_.front();
    const ssize_t sent = send(client_fd_, frame.data() + tx_offset_,
                              frame.size() - tx_offset_, MSG_NOSIGNAL);
    if (sent > 0) {
      tx_offset_ += static_cast<std::size_t>(sent);
      if (tx_offset_ == frame.size()) {
        const unsigned frame_size = static_cast<unsigned>(frame.size());
        tx_queue_.pop_front();
        tx_offset_ = 0;
        ++sent_;
        if (packet_log_) {
          std::fprintf(stderr,
                       "VESP32_TCP_FRAME_SENT bytes=%u queue_remaining=%u\n",
                       frame_size, static_cast<unsigned>(tx_queue_.size()));
          std::fflush(stderr);
        } else if ((sent_ % 80U) == 0U) {
          std::fprintf(stderr,
                       "VESP32_PROGRESS transactions=%u routed=%u sent=%u "
                       "max_queue=%u queued=%u backpressure=%u\n",
                       transactions_, routed_, sent_, max_queue_depth_,
                       static_cast<unsigned>(tx_queue_.size()),
                       backpressure_events_);
          std::fflush(stderr);
        }
        if (ready_pending_ && notify_level_ &&
            tx_queue_.size() < queue_capacity_) {
          std::fprintf(stderr, "VESP32_BACKPRESSURE RELEASE queue=%u\n",
                       static_cast<unsigned>(tx_queue_.size()));
          std::fflush(stderr);
          assert_ready();
        }
      }
    } else if (sent == 0 ||
               (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR)) {
      std::fprintf(stderr, "VESP32_TCP_DISCONNECTED send: %s\n",
                   sent == 0 ? "peer closed" : std::strerror(errno));
      std::fflush(stderr);
      disconnect_client("send_error");
    }
  }

  void disconnect_client(const char *reason) {
    std::fprintf(stderr,"RUNTIME_TCP_DISCONNECT reason=%s queued=%zu\n",reason,tx_queue_.size());
    close_socket(&client_fd_); tx_queue_.clear(); tx_offset_=0; frame_synced_=false;
  }

  BridgeQspi *qspi_;
  BridgeNotifyGpio *notify_;
  Gpio_itf *ready_;
  void *trace_;
  int port_;
  bool packet_log_;
  int network_poll_ps_;
  unsigned queue_capacity_;
  int current_cs_;
  int notify_level_;
  bool handshake_armed_;
  bool ready_pending_;
  bool transaction_handshake_;
  int pending_bits_;
  uint8_t pending_byte_;
  std::vector<uint8_t> transaction_;

  int listen_fd_;
  int client_fd_;
  std::deque<std::vector<uint8_t>> tx_queue_;
  std::size_t tx_offset_;
  unsigned transactions_;
  unsigned routed_;
  unsigned sent_;
  unsigned backpressure_events_;
  unsigned max_queue_depth_;
  unsigned poll_counter_=0;
  bool frame_synced_=false;
  uint64_t unconnected_packets_=0;
};

void BridgeQspi::edge(int64_t timestamp, int data_0, int data_1, int data_2,
                      int data_3, int mask) {
#ifdef STRICT_EDGE_AUDIT
  strict_audit::event(1, timestamp, data_0);
  strict_audit::mix(data_1); strict_audit::mix(data_2);
  strict_audit::mix(data_3); strict_audit::mix(mask);
#endif
  (void)timestamp;
  (void)data_1;
  (void)data_2;
  (void)data_3;
  (void)mask;
  top_->spi_bit(data_0);
}

void BridgeQspi::cs_edge(int64_t timestamp, int cs) {
#ifdef STRICT_EDGE_AUDIT
  strict_audit::event(2, timestamp, cs);
#endif
  top_->cs_edge(timestamp, cs);
}

void BridgeNotifyGpio::edge(int64_t timestamp, int data) {
#ifdef STRICT_EDGE_AUDIT
  strict_audit::event(3, timestamp, data);
#endif
  top_->notify_edge(timestamp, data);
}

extern "C" Dpi_model *dpi_model_new(js::config *config, void *handle) {
  return new CpxSpiBridge(config, handle);
}
