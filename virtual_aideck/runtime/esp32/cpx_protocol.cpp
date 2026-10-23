#include "cpx_protocol.hpp"

namespace cpx {

bool decode_gap8_to_host(const uint8_t *spi_bytes, std::size_t transfer_size,
                         DecodedFrame *decoded, std::string *error) {
  if (spi_bytes == nullptr || decoded == nullptr || error == nullptr) {
    return false;
  }
  if (transfer_size < 4) {
    *error = "SPI transfer shorter than length and CPX route headers";
    return false;
  }

  const std::size_t wire_length =
      static_cast<std::size_t>(spi_bytes[0]) |
      (static_cast<std::size_t>(spi_bytes[1]) << 8);
  if (wire_length < kHeaderSize || wire_length > kSpiMtu) {
    *error = "CPX wire length outside [2, 1022]";
    return false;
  }
  if (wire_length + 2 > transfer_size) {
    *error = "CPX wire length exceeds received SPI transaction";
    return false;
  }
  std::size_t remainder = wire_length > 2 ? wire_length - 2 : 0;
  if (remainder < 4) {
    remainder = 4;
  }
  remainder = (remainder + 3) & ~static_cast<std::size_t>(3);
  const std::size_t expected_transfer_size = 4 + remainder;
  if (transfer_size != expected_transfer_size) {
    *error = "SPI transaction does not match official 4-byte header/padding sequence";
    return false;
  }

  const uint8_t route0 = spi_bytes[2];
  const uint8_t route1 = spi_bytes[3];
  Route route = {
      static_cast<uint8_t>((route0 >> 3) & 0x07),
      static_cast<uint8_t>(route0 & 0x07),
      static_cast<uint8_t>(route1 & 0x3f),
      static_cast<uint8_t>((route1 >> 6) & 0x03),
      (route0 & 0x40) != 0,
  };

  if ((route0 & 0x80) != 0) {
    *error = "reserved CPX route bit is set";
    return false;
  }
  if (route.version != 0) {
    *error = "unsupported CPX version";
    return false;
  }
  if (route.source != kGap8) {
    *error = "unsupported CPX source (expected GAP8)";
    return false;
  }
  if (route.destination != kWifiHost) {
    *error = "unsupported CPX destination (expected WIFI_HOST)";
    return false;
  }
  if (route.function != kApp) {
    *error = "unsupported CPX function (expected APP)";
    return false;
  }
  if (!route.last_packet) {
    *error = "fragmented CPX packets are not supported by this model";
    return false;
  }

  decoded->route = route;
  decoded->wire_frame.assign(spi_bytes, spi_bytes + wire_length + 2);
  return true;
}

}  // namespace cpx
