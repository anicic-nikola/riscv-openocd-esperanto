#ifndef SOCKET_DMI_H
#define SOCKET_DMI_H

#include "jtag/drivers/riscv_dtm/dtm.h"
#include "helper/command.h"

int socket_dmi_init(dtm_driver_t *driver);
int socket_dmi_deinit(dtm_driver_t *driver);
int socket_dmi_read_dmi(dtm_driver_t *driver, uint32_t *data, uint32_t address);
int socket_dmi_write_dmi(dtm_driver_t *driver, uint32_t address, uint32_t data);
int register_socket_dtm_driver(void);

int socket_transport_initialize(void);
#endif // SOCKET_DMI_H
