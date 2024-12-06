#include "dtm.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <helper/command.h>
#include <helper/log.h>
#include "transport/transport.h"
#include "jtag/interface.h"

#define MAX_DTM_DRIVERS 10

static dtm_driver_t *registered_drivers[MAX_DTM_DRIVERS];
static int driver_count = 0;

static dtm_driver_t *active_driver = NULL;

int register_dtm_driver(dtm_driver_t *driver) {
    if (driver_count >= MAX_DTM_DRIVERS) {
        fprintf(stderr, "Maximum number of DTM drivers reached.\n");
        return ERROR_FAIL;
    }
    registered_drivers[driver_count++] = driver;
    return ERROR_OK;
}

// Retrieve a DTM driver by name
dtm_driver_t *get_dtm_driver(const char *name) {
    for (int i = 0; i < driver_count; i++) {
        if (strcmp(registered_drivers[i]->name, name) == 0) {
            return registered_drivers[i];
        }
    }
    return NULL;
}

int select_dtm_driver(const char *name) {
    dtm_driver_t *driver = get_dtm_driver(name);
    if (!driver) {
        fprintf(stderr, "DTM driver '%s' not found.\n", name);
        return ERROR_FAIL;
    }

    if (driver->init(driver) != 0) {
        fprintf(stderr, "Failed to initialize DTM driver '%s'.\n", name);
        return ERROR_FAIL;
    }

    if (active_driver && active_driver->deinit) {
        active_driver->deinit(active_driver);
    }

    active_driver = driver;
    return ERROR_OK;
}

dtm_driver_t *get_active_dtm_driver(void) {
    return active_driver;
}


static int riscv_dtm_initialize(void) {
    struct transport *current_transport = get_current_transport();
    if (!current_transport) {
        LOG_ERROR("No transport selected.");
        return ERROR_FAIL;
    }

    const char *transport_name = current_transport->name;

    if (select_dtm_driver(transport_name) != ERROR_OK) {
        LOG_ERROR("Failedriverd to select DTM driver '%s'", transport_name);
        return ERROR_FAIL;
    }

    dtm_driver_t *driver = get_active_dtm_driver();
    if (driver && driver->init) {
        if (driver->init(driver) != ERROR_OK) {
            LOG_ERROR("Failed to initialize DTM driver '%s'", transport_name);
            return ERROR_FAIL;
        }
    } else {
        LOG_ERROR("No active DTM driver or init function missing.");
        return ERROR_FAIL;
    }

    LOG_INFO("DTM Adapter initialized with transport '%s'", transport_name);

    return ERROR_OK;
}

static int riscv_dtm_free(void) {
    active_driver = get_active_dtm_driver();
    active_driver->deinit(active_driver);
    return ERROR_OK;
}

static const char * const riscv_dtm_transports[] = { "jtag", "socket", "pcie", NULL };

struct adapter_driver riscv_dtm_adapter_driver = {
	.name = "riscv_dtm",
	.transports = riscv_dtm_transports,

	.init = riscv_dtm_initialize,
	.quit = riscv_dtm_free,
};