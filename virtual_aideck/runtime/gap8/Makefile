APP = aideck_runtime
APP_SRCS = main.c
SESSION_US ?= 3600000000
APP_CFLAGS += -O3 -g -DCAMERA_SESSION_ID=$(SESSION_ID)ULL -DRUNTIME_SESSION_US=$(SESSION_US)ULL -DTIMESTAMP_AUDIT=0 -DBENCH_SPI_MHZ=30 -DBENCH_FRAMES=2 -DBENCH_VERIFY_FNV=0
ROOT := $(abspath ../../..)
RUNTIME := $(ROOT)/virtual_aideck/runtime
BUILD_MODEL := $(RUNTIME)/build
export PYTHONPATH := $(RUNTIME)/state_link/virtual_uart:$(RUNTIME)/esp32:$(PYTHONPATH)
override config_args += --config-opt=runner/peripherals=true
override config_args += --config-opt=board/devices/camera/module=$(BUILD_MODEL)/live_camera.so
override config_args += --config-opt=board/devices/wifi/generator=cpx_esp32_gen
override config_args += --config-opt=board/devices/wifi/gpio_notify=gpio3
override config_args += --config-opt=board/devices/wifi/config/module=$(BUILD_MODEL)/cpx_spi_bridge.so
override config_args += --config-opt=board/devices/wifi/config/port=5000
override config_args += --config-opt=board/devices/wifi/config/packet_log=0
NETWORK_POLL_US ?= 10
override config_args += --config-opt=board/devices/wifi/config/network_poll_ps=$(NETWORK_POLL_US)000000
override config_args += --config-opt=board/devices/wifi/config/queue_capacity=10
FRAME_ASSOCIATION ?= 0
FRAME_STATE_SEND ?= 0
STATE_LINK ?= 0
ifeq ($(STATE_LINK),1)
APP_CFLAGS += -DFRAME_ASSOCIATION=$(FRAME_ASSOCIATION) -DFRAME_STATE_SEND=$(FRAME_STATE_SEND)
ifeq ($(FRAME_ASSOCIATION),1)
APP_SRCS += frame_state/association.c
endif
APP_SRCS += ego_state/receiver.c ../state_link/common/snapshot.c ../state_link/common/link.c
APP_CFLAGS += -DEGO_STATE_FAULTS=$(STATE_FAULTS) -DEGO_STATE_LINK=1 -DEGO_STATE_DIAGNOSTICS=$(STATE_DIAGNOSTICS) -I$(RUNTIME)/state_link/common
STATE_DIAGNOSTICS ?= 0
STATE_FAULTS ?= 0
override config_args += --config-opt=board/devices/uart/generator=state_uart_gen
endif
include $(RULES_DIR)/pmsis_rules.mk
