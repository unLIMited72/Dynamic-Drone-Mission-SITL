#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace cpx {

constexpr std::size_t kSpiMtu = 1022;
constexpr std::size_t kHeaderSize = 2;
constexpr uint8_t kGap8 = 4;
constexpr uint8_t kWifiHost = 3;
constexpr uint8_t kApp = 5;

struct Route {
  uint8_t source;
  uint8_t destination;
  uint8_t function;
  uint8_t version;
  bool last_packet;
};

struct DecodedFrame {
  Route route;
  std::vector<uint8_t> wire_frame;
};

bool decode_gap8_to_host(const uint8_t *spi_bytes, std::size_t transfer_size,
                         DecodedFrame *decoded, std::string *error);

}  // namespace cpx
