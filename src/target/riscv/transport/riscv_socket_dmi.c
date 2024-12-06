#include "riscv_socket_dmi.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include <arpa/inet.h>
#include "transport/transport.h"
#include "target/target.h"
#include "target/riscv/riscv.h"
#include "helper/log.h"

typedef struct {
    int sockfd;
    char host[256];
    int port;
} socket_priv_t;

// Commands for serialized socket message
#define READ_COMMAND 0x00
#define WRITE_COMMAND 0x01

int socket_dmi_init(dtm_driver_t *driver) {
    // Example: parse host and port from driver->priv (assuming it's a config string)
    // For simplicity, using default values
    const char *default_host = "localhost";
    int default_port = 5555;

    socket_priv_t *priv = malloc(sizeof(socket_priv_t));
    if (!priv) {
        fprintf(stderr, "Failed to allocate memory for socket_priv_t.\n");
        return -1;
    }

    strncpy(priv->host, default_host, sizeof(priv->host) - 1);
    priv->host[sizeof(priv->host) - 1] = '\0';
    priv->port = default_port;

    priv->sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (priv->sockfd < 0) {
        perror("Socket creation failed");
        free(priv);
        return -1;
    }

    struct sockaddr_in server_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(priv->port);

    if (inet_pton(AF_INET, priv->host, &server_addr.sin_addr) <= 0) {
        perror("Invalid address/ Address not supported");
        close(priv->sockfd);
        free(priv);
        return -1;
    }

    if (connect(priv->sockfd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("Connection Failed");
        close(priv->sockfd);
        free(priv);
        return -1;
    }

    driver->priv = priv;
    return 0;
}

int socket_dmi_deinit(dtm_driver_t *driver) {
    if (!driver->priv) {
        return -1;
    }

    socket_priv_t *priv = (socket_priv_t *)driver->priv;
    close(priv->sockfd);
    free(priv);
    driver->priv = NULL;
    return 0;
}

int socket_dmi_read_dmi(dtm_driver_t *driver, uint32_t *data, uint32_t address) {
    if (!driver->priv) {
        return -1;
    }

    socket_priv_t *priv = (socket_priv_t *)driver->priv;
    uint8_t buffer[8];
    // Protocol: [address][read command]
    buffer[0] = READ_COMMAND; 
    buffer[1] = (address >> 24) & 0xFF;
    buffer[2] = (address >> 16) & 0xFF;
    buffer[3] = (address >> 8) & 0xFF;
    buffer[4] = address & 0xFF;
    // Reserved bytes
    buffer[5] = 0x00;
    buffer[6] = 0x00;
    buffer[7] = 0x00;

    ssize_t sent = send(priv->sockfd, buffer, sizeof(buffer), 0);
    if (sent != sizeof(buffer)) {
        perror("Failed to send read DMI command");
        return -1;
    }

    ssize_t received = recv(priv->sockfd, buffer, sizeof(buffer), 0);
    if (received != sizeof(buffer)) {
        perror("Failed to receive read DMI response");
        return -1;
    }

    *data = (buffer[0] << 24) |
            (buffer[1] << 16) |
            (buffer[2] << 8) |
            buffer[3];

    return 0;
}

int socket_dmi_write_dmi(dtm_driver_t *driver, uint32_t address, uint32_t data) {
    if (!driver->priv) {
        return -1;
    }

    socket_priv_t *priv = (socket_priv_t *)driver->priv;
    uint8_t buffer[8];
    // Protocol: [address][write command][data]
    buffer[0] = WRITE_COMMAND;
    buffer[1] = (address >> 24) & 0xFF;
    buffer[2] = (address >> 16) & 0xFF;
    buffer[3] = (address >> 8) & 0xFF;
    buffer[4] = address & 0xFF;
    buffer[5] = (data >> 24) & 0xFF;
    buffer[6] = (data >> 16) & 0xFF;
    buffer[7] = (data >> 8) & 0xFF; // Assuming only 24 bits of data for this example

    ssize_t sent = send(priv->sockfd, buffer, sizeof(buffer), 0);
    if (sent != sizeof(buffer)) {
        perror("Failed to send write DMI command");
        return -1;
    }

    // Optionally, handle acknowledgment from the server
    // For simplicity, we'll assume it's successful
    return 0;
}

static dtm_driver_t socket_driver = {
    .name = "socket",
    .init = socket_dmi_init,
    .deinit = socket_dmi_deinit,
    .read_dmi = socket_dmi_read_dmi,
    .write_dmi = socket_dmi_write_dmi,
    .priv = NULL
};


int socket_dmi_read(struct target *target, uint32_t *data, uint32_t address) {
    return socket_dmi_read_dmi(&socket_driver, data, address);
}

int socket_dmi_write(struct target *target, uint32_t address, uint32_t data) {
    return socket_dmi_write_dmi(&socket_driver, address, data);
}

static const struct command_registration socket_transport_command_handlers[] = {
	{
		.name = "socket",
		.mode = COMMAND_ANY,
		.help = "perform socket adapter actions",
		.usage = "",
	},
	COMMAND_REGISTRATION_DONE
};


static int socket_transport_select(struct command_context *ctx) {
    struct target *target = get_current_target(ctx);
    if (!target){
        LOG_ERROR("Target not yet selected, socket transport will wait.");
        return ERROR_FAIL;
    }

    // if (strcmp(target->type->name, "riscv") != 0) {
    //     LOG_DEBUG("Target is not a riscv target, skipping socket transport.");
    //     return ERROR_OK; // or ERROR_FAIL depending on your policy
    // }

    LOG_INFO("Selected socket transport for RISC-V target.");
    RISCV_INFO(r);
    r->dmi_read = socket_dmi_read;
    r->dmi_write = socket_dmi_write;
    return register_commands(ctx, NULL, socket_transport_command_handlers);
    // return ERROR_OK;
}

static int socket_transport_init(struct command_context *cmd_ctx)
{
    if (socket_dmi_init(&socket_driver) != 0) {
        LOG_ERROR("Failed to register socket DMI driver.");
        return ERROR_FAIL;
    } else {
        LOG_DEBUG("Socket DMI driver registered successfully.");
    }

    //return socket_dmi_init(&socket_driver);
    return ERROR_OK;
}

int register_socket_dtm_driver(void) {
    return register_dtm_driver(&socket_driver);
}

static struct transport socket_transport = {
    .name = "socket",
    .select = socket_transport_select,
    .init = socket_transport_init,
    .next = NULL,
};

int socket_transport_register(void) {
    return transport_register(&socket_transport);
}

int socket_transport_initialize(void) {
    LOG_DEBUG("Initializing socket DTM driver.");
    if (register_socket_dtm_driver() != 0) {
        LOG_ERROR("Failed to register socket DTM driver.");
        return ERROR_FAIL;
    } else {
        LOG_DEBUG("Socket DTM driver registered successfully.");
    }

    LOG_DEBUG("Initializing socket transport.");
    if (socket_transport_register() != ERROR_OK) {
        LOG_ERROR("Failed to register socket transport.");
        return ERROR_FAIL;
    } else {
        LOG_DEBUG("Socket transport registered successfully.");
    }

    return ERROR_OK;

}

static void socket_constructor(void) __attribute__ ((constructor));
static void socket_constructor(void)
{
    if(socket_transport_initialize() != 0){
        LOG_ERROR("Failed to initialize socket transport!");
    }
    LOG_DEBUG("Socket transport successfully initialized.");
}

// __attribute__((constructor))
// static void init_socket_dtm_driver(void) {
//     LOG_DEBUG("Initializing socket DTM driver.");
//     if (register_socket_dtm_driver() != 0) {
//         LOG_ERROR("Failed to register socket DTM driver.");
//     } else {
//         LOG_DEBUG("Socket DTM driver registered successfully.");
//     }

//     LOG_DEBUG("Initializing socket transport.");
//     if (socket_transport_register() != ERROR_OK) {
//         LOG_ERROR("Failed to register socket transport.");
//     } else {
//         LOG_DEBUG("Socket transport registered successfully.");
//     }
// }

bool transport_is_socket(void)
{
	return get_current_transport() == &socket_transport;
}