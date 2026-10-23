#pragma once
#include <cstdint>
#include <cstdio>
namespace strict_audit {
static uint64_t digest=14695981039346656037ULL, bits=0, cs=0, gpio=0, ready=0;
static int64_t previous=-1, minimum=INT64_MAX;
static void mix(uint64_t value) { digest=(digest^value)*1099511628211ULL; }
static void event(unsigned kind, int64_t timestamp, int value) {
  mix(kind); mix(timestamp); mix(value);
  if(kind==1) {
    ++bits;
    if(previous>=0 && timestamp>previous && timestamp-previous<minimum) minimum=timestamp-previous;
    previous=timestamp;
  }
  if(kind==2) ++cs;
  if(kind==3) ++gpio;
  if(kind==4) ++ready;
}
static void report() {
  std::fprintf(stderr,"STRICT_EDGE_AUDIT bits=%llu cs=%llu gpio=%llu ready=%llu digest=%016llx min_bit_delta_ps=%lld\n",
    (unsigned long long)bits,(unsigned long long)cs,(unsigned long long)gpio,
    (unsigned long long)ready,(unsigned long long)digest,(long long)minimum);
}
}
