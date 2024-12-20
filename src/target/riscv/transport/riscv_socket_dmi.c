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

// Response codes
#define RESPONSE_OK 0x00
#define RESPONSE_ERROR 0x01

#define DEFAULT_SOCKET_HOST "127.0.0.1"
#define DEFAULT_SOCKET_PORT 5555

static int transportIsRegistered = -1;

// Helper function to receive data with error handling
static int recv_all(int sockfd, void *buf, size_t len) {
    size_t to_read = len;
    while (to_read > 0) {
        ssize_t bytes_read = recv(sockfd, buf, to_read, 0);
        if (bytes_read <= 0) {
            if (bytes_read == 0) {
                LOG_ERROR("Socket closed by remote host");
            } else {
                LOG_ERROR("recv error: %s", strerror(errno));
            }
            return ERROR_FAIL;
        }
        buf = (char*)buf + bytes_read;
        to_read -= bytes_read;
    }
    return ERROR_OK;
}

static int socket_dmi_connect(dtm_driver_t* driver){
    if (!driver->priv) {
        return ERROR_FAIL;
    }

    socket_priv_t *priv = (socket_priv_t *)driver->priv;
    if (priv->sockfd != -1) {
        LOG_WARNING("Already connected, close it first.");
        close(priv->sockfd);
        priv->sockfd = -1;
    }

    priv->sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (priv->sockfd < 0) {
        perror("Socket creation failed");
        return ERROR_FAIL;
    }

    struct sockaddr_in server_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(priv->port);

    if (inet_pton(AF_INET, priv->host, &server_addr.sin_addr) <= 0) {
        perror("Invalid address/ Address not supported");
        close(priv->sockfd);
        priv->sockfd = -1;
        return ERROR_FAIL;
    }

    if (connect(priv->sockfd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("Connection Failed");
        close(priv->sockfd);
        priv->sockfd = -1;
        return ERROR_FAIL;
    }

    return ERROR_OK;
}

int socket_dmi_init(dtm_driver_t *driver) {
    // Use default values for now and later see if there is something in the openocd config file to connect with
    // like socket specified host and port from the config file
    socket_priv_t *priv = malloc(sizeof(socket_priv_t));
    if (!priv) {
        LOG_ERROR("Failed to allocate memory for socket_priv_t.");
        return ERROR_FAIL;
    }

    strncpy(priv->host, DEFAULT_SOCKET_HOST, sizeof(priv->host) - 1);
    priv->host[sizeof(priv->host) - 1] = '\0';
    priv->port = DEFAULT_SOCKET_PORT;

    priv->sockfd = -1; // Initialize to -1 to indicate not connected yet
    driver->priv = priv;
    return ERROR_OK;
}


int socket_dmi_deinit(dtm_driver_t *driver) {
    if (!driver->priv) {
        return ERROR_FAIL;
    }

    socket_priv_t *priv = (socket_priv_t *)driver->priv;
    if (priv->sockfd != -1) {
        close(priv->sockfd);
    }
    free(priv);
    driver->priv = NULL;
    return ERROR_OK;
}

int socket_dmi_read_dmi(dtm_driver_t *driver, uint32_t *data, uint32_t address) {
    if (!driver->priv) {
        return ERROR_FAIL;
    }

    socket_priv_t *priv = (socket_priv_t *)driver->priv;

    // Check if connected and connect if necessary
    if (priv->sockfd == -1) {
        if (socket_dmi_connect(driver) != 0) {
            LOG_ERROR("Not connected and unable to establish connection.");
            return -1;
        }
    }
    uint8_t buffer[9];
    // Protocol: [READ_COMMAND][address (4 bytes)][data_length (1 byte, fixed as 4 for now)][Reserved (3 bytes)]
    buffer[0] = READ_COMMAND; 
    buffer[1] = (address >> 24) & 0xFF;
    buffer[2] = (address >> 16) & 0xFF;
    buffer[3] = (address >> 8) & 0xFF;
    buffer[4] = address & 0xFF;
    buffer[5] = 4; // data length in bytes (fixed at 4)
    // Reserved bytes
    buffer[6] = 0x00;
    buffer[7] = 0x00;
    buffer[8] = 0x00;

    ssize_t sent = send(priv->sockfd, buffer, sizeof(buffer), 0);
    if (sent != sizeof(buffer)) {
        perror("Failed to send read DMI command");
        return ERROR_FAIL;
    }

    if (recv_all(priv->sockfd, buffer, 1) != 0) {
        return -1;
    }
    if (buffer[0] != RESPONSE_OK) {
        LOG_ERROR("DMI read failed (error code: 0x%X)", buffer[0]);
        return -1;
    }

    // Now, receive data
    if (recv_all(priv->sockfd, buffer, 4) != 0) {
        return -1;
    }

    *data = (buffer[1] << 24) |
            (buffer[2] << 16) |
            (buffer[3] << 8) |
            buffer[4];

    return ERROR_OK;
}

int socket_dmi_write_dmi(dtm_driver_t *driver, uint32_t address, uint32_t data) {
    if (!driver->priv) {
        return ERROR_FAIL;
    }

    socket_priv_t *priv = (socket_priv_t *)driver->priv;

    // Check if connected and connect if necessary
    if (priv->sockfd == -1) {
        if (socket_dmi_connect(driver) != 0) {
            LOG_ERROR("Not connected and unable to establish connection.");
            return -1;
        }
    }
    uint8_t buffer[10];
    // Protocol: [WRITE_COMMAND][address (4 bytes)][data_length (1 byte, fixed as 4 for now)][data (4 bytes)]
    buffer[0] = WRITE_COMMAND;
    buffer[1] = (address >> 24) & 0xFF;
    buffer[2] = (address >> 16) & 0xFF;
    buffer[3] = (address >> 8) & 0xFF;
    buffer[4] = address & 0xFF;
    buffer[5] = 4; // data length in bytes (fixed at 4)
    buffer[6] = (data >> 24) & 0xFF;
    buffer[7] = (data >> 16) & 0xFF;
    buffer[8] = (data >> 8) & 0xFF;
    buffer[9] = data & 0xFF;

    ssize_t sent = send(priv->sockfd, buffer, sizeof(buffer), 0);
    if (sent != sizeof(buffer)) {
        perror("Failed to send write DMI command");
        return ERROR_FAIL;
    }

    // Receive response code
    if (recv_all(priv->sockfd, buffer, 1) != 0) {
        return -1;
    }

    if (buffer[0] != RESPONSE_OK) {
        LOG_ERROR("DMI write failed (error code: 0x%X)", buffer[0]);
        return -1;
    }

    return ERROR_OK;
}

COMMAND_HANDLER(command_socket_host){
	if (CMD_ARGC != 1)
		return ERROR_COMMAND_SYNTAX_ERROR;
    dtm_driver_t *active_driver = get_active_dtm_driver();
    if (!active_driver || strcmp(active_driver->name, "socket") != 0) {
        LOG_ERROR("Active DTM driver is not socket");
        return ERROR_FAIL;
    }
    socket_priv_t *priv = (socket_priv_t*)active_driver->priv;
    strncpy(priv->host, CMD_ARGV[0], sizeof(priv->host) - 1);
    priv->host[sizeof(priv->host) - 1] = '\0';
    return ERROR_OK;
}

COMMAND_HANDLER(command_socket_port){
	if (CMD_ARGC != 1)
		return ERROR_COMMAND_SYNTAX_ERROR;
    dtm_driver_t *active_driver = get_active_dtm_driver();
    if (!active_driver || strcmp(active_driver->name, "socket") != 0) {
        LOG_ERROR("Active DTM driver is not socket'");
        return ERROR_FAIL;
    }

    socket_priv_t *priv = (socket_priv_t*)active_driver->priv;
    priv->port = atoi(CMD_ARGV[0]);
    return ERROR_OK;
}

COMMAND_HANDLER(command_socket_connect){
    dtm_driver_t *active_driver = get_active_dtm_driver();
    if (!active_driver || strcmp(active_driver->name, "socket") != 0) {
        LOG_ERROR("Active DTM driver is not socket");
        return ERROR_FAIL;
    }

    if (socket_dmi_connect(active_driver) != 0) {
        LOG_ERROR("Failed to connect to socket.");
        return ERROR_FAIL;
    }

    return ERROR_OK;
}

static int socket_dtm_set_transport(struct transport *transport)
{
    // This function is called to set the transport
    // In this case, we should verify the transport is "socket"
    if (strcmp(transport->name, "socket") != 0) {
        LOG_ERROR("transport->name != socket in socket_dtm_set_transport");
        return ERROR_FAIL;
    }

    return ERROR_OK;
}

static dtm_driver_t socket_driver __attribute__((used)) = {
    .name = "socket",
    .init = socket_dmi_init,
    .deinit = socket_dmi_deinit,
    .read_dmi = socket_dmi_read_dmi,
    .write_dmi = socket_dmi_write_dmi,
    .set_transport = socket_dtm_set_transport,
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
        .name = "host",
        .mode = COMMAND_ANY,
        .help = "Set the hostname for the socket connection",
        .usage = "<hostname>",
        .handler = command_socket_host,
    },
    {
        .name = "port",
        .mode = COMMAND_ANY,
        .help = "Set the port for the socket connection",
        .usage = "<port>",
        .handler = command_socket_port,
    },
    {
        .name = "connect",
        .mode = COMMAND_ANY,
        .help = "Connect to the socket server",
        .usage = "",
        .handler = command_socket_connect,
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

static struct transport socket_transport __attribute__((used)) = {
    .name = "socket",
    .select = socket_transport_select,
    .init = socket_transport_init,
    .next = NULL,
};

int socket_transport_register(void) {
    return transport_register(&socket_transport);
}

int register_socket_dtm_driver(void) {
    return register_dtm_driver(&socket_driver);
}

int register_riscv_socket_transport(void) {
    LOG_DEBUG("Initializing socket DTM driver.");
    if (register_socket_dtm_driver() != 0) {
        LOG_ERROR("Failed to register socket DTM driver.");
        return ERROR_FAIL;
    } else {
        LOG_DEBUG("Socket DTM driver registered successfully.");
    }

    if (transportIsRegistered != -1){
        LOG_DEBUG("Socket transport already registered successfully.");
        return ERROR_OK;
    }
    LOG_DEBUG("Initializing socket transport.");
    if (socket_transport_register() != ERROR_OK) {
        LOG_ERROR("Failed to register socket transport.");
        return ERROR_FAIL;
    } else {
        transportIsRegistered = 1;
        LOG_DEBUG("Socket transport registered successfully.");
    }

    return ERROR_OK;

}

static void socket_constructor(void) __attribute__ ((constructor));
static void socket_constructor(void)
{
    if(register_riscv_socket_transport() != 0){
        LOG_ERROR("Failed to initialize socket transport!");
    }
    LOG_DEBUG("Socket transport successfully initialized.");
}

bool transport_is_socket(void)
{
	return get_current_transport() == &socket_transport;
}