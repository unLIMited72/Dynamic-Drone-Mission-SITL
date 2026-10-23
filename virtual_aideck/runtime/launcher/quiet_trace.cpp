// GVSoC-only interposition of disabled diagnostic formatting. No device/event
// functions are replaced. vp::trace is the actual handle type in dpi_wrapper.
// Opt-in LD_PRELOAD; do not use with SystemVerilog/other DPI providers.
#include "vp/vp.hpp"
#include "dpi/models.hpp"
#include <cstdarg>
#include <cstdio>
#include <vector>

extern "C" void dpi_trace_msg(void *, int, const char *);
#ifdef STRICT_TRACE_PROFILE
static unsigned long long skipped=0, formatted=0;
__attribute__((destructor)) static void trace_counts() {
  if (skipped || formatted)
    std::fprintf(stderr,"STRICT_TRACE_PROFILE skipped=%llu formatted=%llu\n",skipped,formatted);
}
#endif

void Dpi_model::trace_msg(void *trace, int level, const char *format, ...) {
  // is_active is checked by the original trace sink too. Do not suppress active
  // traces or alter their level filtering, output order, or formatting.
  if (!static_cast<vp::trace *>(trace)->is_active) {
#ifdef STRICT_TRACE_PROFILE
    ++skipped;
#endif
    return;
  }
#ifdef STRICT_TRACE_PROFILE
  ++formatted;
#endif
  char buffer[1024];
  va_list args;
  va_start(args, format);
  int size = vsnprintf(buffer, sizeof(buffer), format, args);
  va_end(args);
  if (size < 0) return;
  if (static_cast<size_t>(size) < sizeof(buffer)) {
    dpi_trace_msg(trace, level, buffer);
  } else {
    std::vector<char> full(static_cast<size_t>(size) + 1);
    va_start(args, format);
    vsnprintf(full.data(), full.size(), format, args);
    va_end(args);
    dpi_trace_msg(trace, level, full.data());
  }
}
