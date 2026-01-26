/**
 *   @file  firmware_sram_download.c
 *
 *   @brief
 *      APIs Implementation of Host Interface Message.
 *
 *  \par
 *  NOTE:
 *      (C) Copyright 2025 Possumic, Inc.
 *
 */

#include "vendor_porting_layer.h"

#if (CONFIG_FW_DOWNLOAD_SRAM == 1)

#define IMAGE_BUF_SIZE			(1024)  /* data and size must be align to 32bit. */
#define FWDL_RETRY_CNT			3
static uint8_t g_fw_image_buf[IMAGE_BUF_SIZE];

static int fwdl_send_start_msg(uint16_t mtu_size, uint32_t fw_size)
{
    struct fwdl_start_cmd_t fwdl_start_cmd = {
        .dl_cmd = FW_DOWNLOAD_CTRL_START_SUB_CMD,
        .dl_flag = FW_DOWNLOAD_CTRL_AUTORUN_FLAG,
        .dl_len = mtu_size,
        .total_size = fw_size
    };
    return fwdl_send_hif_msg(FW_DOWNLOAD_CTRL_CMD, (uint8_t *)&fwdl_start_cmd, sizeof(struct fwdl_start_cmd_t));
}

static int fwdl_send_data_msg(uint8_t *data, uint32_t fw_size)
{
    int ret = 0;
    uint32_t pos = 0;
    while (fw_size) {
        if (fw_size >= FWDL_DOWNLOAD_MTU_SIZE) {
            ret = fwdl_send_hif_msg(FW_DOWNLOAD_DATA_CMD, (uint8_t *)&data[pos], FWDL_DOWNLOAD_MTU_SIZE);
            pos += FWDL_DOWNLOAD_MTU_SIZE;
            fw_size -= FWDL_DOWNLOAD_MTU_SIZE;
        } else {
            ret = fwdl_send_hif_msg(FW_DOWNLOAD_DATA_CMD, (uint8_t *)&data[pos], fw_size);
            fw_size = 0;
        }
    }
    return ret;
}

int fw_download_data(uint8_t *data, uint16_t length)
{
    int ret;
    hif_debug_verb("goto download data size %d\n", length);
    ret = fwdl_send_data_msg(data, length);
    if (ret < 0) {
        hif_debug_log("fw download data fail ret %d", ret);
    }
    return ret;
}

int fw_download_start(uint32_t fw_total_size)
{
    int ret;

    ret = fw_download_init();
    if (ret < 0) {
        hif_debug_log("%s, interface driver init fail", __FUNCTION__);
        goto exit;
    }

    hif_debug_verb("goto to sync\n");
    ret = fw_download_sync(CONFIG_FW_DOWNLOAD_SYNC_RETRY);
    if (ret < 0) {
        hif_debug_log("%s, sync fail", __FUNCTION__);
        goto exit;
    }

    hif_debug_verb("goto send download start command\n");
    ret = fwdl_send_start_msg(FWDL_DOWNLOAD_MTU_SIZE, fw_total_size);
    if (ret < 0) {
        hif_debug_log("fw download start cmd fail\n");
    }

exit:
    hif_debug_log("fw download start end, ret = %d\n", ret);
    return ret;
}

int firmware_download(void)
{
	int ret;
	uint32_t image_offset, read_size, image_size = fw_image_size_read();
	ret = fw_download_start(image_size);
    if (ret < 0) {
        hif_debug_log("download start fail size %d\n", image_size);
        return ret;
    }
	image_offset = 0;
	while (image_size) {
		if (image_size >= IMAGE_BUF_SIZE) {
			read_size = IMAGE_BUF_SIZE;
		} else {
			read_size = image_size;
		}
		ret = fw_image_read(image_offset, (uint8_t *)&g_fw_image_buf[0], read_size);
		if (ret) {
			hif_debug_log("read image fail offset %d read_size %d\n", image_offset, read_size);
			return ret;
		}
		ret = fw_download_data((uint8_t *)&g_fw_image_buf[0], read_size);
		if (ret) {
			hif_debug_log("download fail offset %d read_size %d\n", image_offset, read_size);
			return ret;
		}
		image_size -= read_size;
		image_offset += read_size;
	}
	return 0;
}

int sensor_download(void)
{
	int ret;
	int retry = FWDL_RETRY_CNT;
	do {
		/*retry sync for 100 times*/
		ret = fw_download_sync(100);
		if (ret < 0) {
			hif_debug_log("firmware download sync fail\n");
		} else {
			/*reboot mmwave firmware to prepare firmware download, retry 3 times*/
			ret = fw_download_reset(3);
#if CONFIG_HOST_IIC_EN
			/* wait 750ms to reset */
			hif_delay_us(750000);
#else
			/* wait 50ms to reset */
			hif_delay_us(50000);
#endif
			if (ret < 0) {
				hif_debug_log("firmware download reset fail\n");
			} else {
				ret = firmware_download();
				if (ret == 0) {
					break;
				}
			}
		}
	} while (retry--);

	hif_debug_log("%s ret %d\n", __FUNCTION__, ret);
	return ret;
}

#endif /* CONFIG_FW_DOWNLOAD_SRAM == 1 */

