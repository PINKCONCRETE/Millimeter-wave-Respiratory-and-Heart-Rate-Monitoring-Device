/*
 *   @file  fw_download.h
 *
 *   @brief
 *      Header file for Host Interface Message Definition.
 *
 *  \par
 *  NOTE:
 *      (C) Copyright 2022 Possumic, Inc.
 *
 */
#ifndef __FW_DOWNLOAD_H__
#define __FW_DOWNLOAD_H__

/* Include Files */

#ifdef __cplusplus
extern "C" {
#endif

#define CONFIG_FW_DOWNLOAD_SRAM          (1)

/* firmware download user config as actual request */
#define CONFIG_FW_DOWNLOAD_SYNC_RETRY    (100)
#define CONFIG_FW_DOWNLOAD_SYNC_TO       (100000) // UINIT US
#define CONFIG_WAIT_ACK_PENDING_TIME     (20000)
#define CONFIG_FWDL_ACK_TIMEOUT          (2000000) //us
#define CONFIG_FWDL_ACK_RETRY_CNT        (3)

/*config to save heap memory by send data segments */
#define CONFIG_SAVE_MEMORY_ENA          (1)

/* firmware download cmd */
#define FWDL_DOWNLOAD_MTU_SIZE                  (0x410)
#define FWDL_FLASH_ERASE_SIZE                   (0x1000)
#define FWDL_FLASH_WRITE_SIZE                   (0x400)
#define FW_DOWNLOAD_RESET_CMD                   0x04
#define FW_DOWNLOAD_CTRL_CMD                    0x0E  /**< Firmware download control */
#define FW_DOWNLOAD_DATA_CMD                    0x0F  /**< Firmware download data packets */

#define FW_FLASH_ERASE_CMD                      0x15  /**< Firmware flash data erase */
#define FW_FLASH_ERASE_TYPE_4K                  1
#define FW_FLASH_ERASE_TYPE_32K                 2
#define FW_FLASH_ERASE_TYPE_64K                 3
#define FW_FLASH_WRITE_CMD                      0x16  /**< Firmware flash data write */
#define FW_FLASH_READ_CMD                       0x17  /**< Firmware flash data read  */
#define FW_DOWNLOAD_SOFT_RESET_SUB_CMD          (0)
#define FW_DOWNLOAD_SENSOR_RESET_SUB_CMD        (1)
#define FW_DOWNLOAD_DEV_RESET_SUB_CMD           (2)
#define FW_DOWNLOAD_CHIP_RESET_SUB_CMD          (3)
#define FW_DOWNLOAD_WDG_RESET_SUB_CMD           (4)
#define FW_DOWNLOAD_SCHED_RESET_SUB_CMD         (5)

#define FW_DOWNLOAD_CTRL_START_SUB_CMD          0x01
#define FW_DOWNLOAD_CTRL_AUTORUN_FLAG           0x01
#define FW_DOWNLOAD_CTRL_UPLOAD_FLAG            0x01

#define IMAGE_HEADER_MAGIC                      0x5350
typedef struct {
    uint16_t magic;
    uint8_t  ver;
    uint8_t  flag;
    uint32_t size;
} image_info_t;

#if CONFIG_FW_BEFORE_1013
#define TLV_HEADER_MAGIC                        0x54
typedef struct {
    uint8_t  magic;
    uint8_t  ver;
    uint16_t size;
} tlv_info_t;
#else
#define TLV_HEADER_MAGIC                        0x50
typedef struct {
    uint8_t  magic;
    uint8_t  reserve[3];
    uint32_t fw_ver;
    uint16_t cli_ver;
    uint16_t size;
} tlv_info_t;
#endif

struct fwdl_reset_cmd_t {
    uint8_t reset_cmd;
    uint8_t pram;
    uint8_t reserved[2];
};

struct fwdl_flash_read_cmd_t {
    uint32_t addr;
    uint32_t len;
};

struct fwdl_flash_erase_cmd_t {
    uint32_t addr;
    uint8_t  erase_type;
    uint8_t  reserved;
    uint16_t block_num;
};

struct fwdl_flash_write_cmd_t {
    uint32_t addr;
    uint32_t len;
};

struct fwdl_start_cmd_t {
    uint8_t  dl_cmd;
    uint8_t  dl_flag;
    uint16_t dl_len;
    uint32_t total_size;
};

int fwdl_send_hif_msg(uint8_t cmd_id, uint8_t *payload, uint16_t length);

/* firmware download user api as follows */
typedef int (*FWDL_INIT_CB_T)(void);
typedef int (*FWDL_WR_CB_T)(uint8_t *pbuff, uint32_t len, uint32_t timeout);
typedef int (*FWDL_RD_CB_T)(uint8_t *pbuff, uint32_t len, uint32_t timeout);
typedef int (*FWDL_IMAGE_READ_CB_T)(uint32_t offset, void *data, uint32_t len);
void fw_download_register(FWDL_INIT_CB_T init_cb, FWDL_WR_CB_T write_cb, FWDL_RD_CB_T read_cb);
void fw_image_read_register(FWDL_IMAGE_READ_CB_T image_read_cb);
int fw_download_init(void);
int fw_download_reset(uint8_t retry);
int fw_download_upload(uint8_t retry);
int fw_download_sync(uint8_t retry_cnt);
int fw_download_start(uint32_t fw_total_size);
int fw_download_data(uint8_t *data, uint16_t length);
int fw_image_read(uint32_t offset, void *data, uint32_t len);
uint32_t fw_image_size_read(void);
uint32_t fw_tlv_size_read(void);
uint16_t fw_image_load_tlv(uint8_t *buff, uint16_t max_size);
void debug_hexdump(char *str_tag, uint8_t *data, uint32_t len);
int sensor_download(void);

/*  << porting guide >>
    step 1: move firmware_download.c and firmware_download.h into project and modify makefile to build them.
    step 2: modify vendor_porting_layer.c and vendor_porting_layer.c to implement vendor driver and os.
            dependes for different platform.
    step 3: call fw_download_register api to register i2c driver or uart dirver, init_cb,write_cb and read_cb should be implement.
    step 4: call fw_download_sync api to sync with mmwave firmware.
    step 5: call fw_download_reset api to warn reset mmwave firmware to prepare firmware download.
    step 6: os_delay 20 ~ 200ms to wait mmware firmware reboot done.
    step 7: call fw_download_start api to sync and send download start command to mmwave firmware.
    step 8: call fw_download_data api to download all image data or segment image data into mmwave fimware.
    <<c files introdution>>
    1.firmware_download.c and firmware_download.h is the implement to download image produces not depends on platfrom driver and os.
    2.vendor_porting_layer.c and vendor_porting_layer.h should be implement by vendor hardware platform and os system.
    3.vendor_test_cmd.c is the test cmd use to test firmware_download api.
    <<points of attention>>
    points 1: "fw_download_register api", init_cb , write_cb and read_cb should be implement or download will crash.
    points 2: "fw_download_data api", param data address shoule be 4 bytes aglin but param length could be any size.
*/
#ifdef __cplusplus
}
#endif

#endif /* __FW_DOWNLOAD_H__ */
