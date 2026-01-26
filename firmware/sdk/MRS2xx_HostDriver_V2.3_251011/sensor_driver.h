/*
 *   @file  mmw_driver.h
 *
 *   @brief
 *      Header file for Host Interface Message Definition.
 *
 *  \par
 *  NOTE:
 *      (C) Copyright 2022 Possumic, Inc.
 *
 */
#ifndef __MMW_RADAR_DRIVER_H__
#define __MMW_RADAR_DRIVER_H__

/* Include Files */

#ifdef __cplusplus
extern "C" {
#endif

#define SENSOR_MODEL_MRS251                                 0
#define SENSOR_MODEL_RS21FD                                 0
#define SENSOR_MODEL_MRS261                                 0
#define SENSOR_MODEL_MRS261L                                0
#define SENSOR_MODEL_RS2111                                 0
#define SENSOR_MODEL_MRS262                                 0
#define SENSOR_MODEL_RS2111FC                               0

#define SENSOR_PRAM_DBG                                     1

#define CFG_DOUT_CTRL_MODE_READ_TARGET_INFO_ENA             (1)
#define CFG_MAX_DUMMY_RETRY                                 (1024)
#define CFG_CONT_DUMMY_RETRY                                (6)
#define CFG_RX_DUMMY_MAGIC                                  (0xFF)

/* hif user config as actual request */
#define CFG_HIF_MAX_RX_TIMEOUT                              (100000) // uinit us
#define CONFIG_HIF_SYNC_TO                                  (100000) // uinit us

#define PUBLIC_UPLOAD_SEL_RANGE                             (BIT(0))
#define PUBLIC_UPLOAD_SEL_MICRO                             (BIT(4))
#define PUBLIC_UPLOAD_SEL_PRES                              (BIT(5))
#define PUBLIC_UPLOAD_SEL_ALL                               (PUBLIC_UPLOAD_SEL_RANGE | PUBLIC_UPLOAD_SEL_MICRO | PUBLIC_UPLOAD_SEL_PRES)
#define PUBLIC_UPLOAD_SEL_NONE                              (0)

#define DOUT_CTRL_MODE                                      (0)
#define DOUT_DATA_MODE                                      (1)

#define DOUT_REPORT_SEL_RANGE                               (BIT(0x01))
#define DOUT_REPORT_SEL_MICRO                               (BIT(0x02))
#define DOUT_REPORT_SEL_PRES                                (BIT(0x03))
#define DOUT_REPORT_SEL_ALL                                 (DOUT_REPORT_SEL_RANGE | DOUT_REPORT_SEL_MICRO | DOUT_REPORT_SEL_PRES)
#define DOUT_REPORT_SEL_NONE                                (0)

#define SECTION_NUM                                         (3)
#define SECTION_STANDBY_ID                                  (0)
#define SECTION_DETECTION_ID                                (1)
#define SECTION_PRESENCE_ID                                 (2)

#define MICRO_DET_MODE                                      (0)
#define MOVE_DET_MODE                                       (1)
#define PRESENCE_DET_MODE                                   (2)
#define EXTERNAL_DET_MODE                                   (3)

#define OUTPUT_NUM                                          (3)
#define OUTPUT_SEL_ID                                       (1)
#define OUTPUT_EN                                           (1)
#define OUTPUT_MODE_LEVEL                                   (0)
#define OUTPUT_MODE_PWM                                     (1)
#define OUTPUT_MODE_PLUES                                   (2)
#define OUTPUT_IO                                           (10)
#define OUTPUT_HAVE_TAGRET_PRAM                             (1)
#define OUTPUT_NO_TAGRET_PRAM                               (0)

/* tlv buff config */
#define TLV_ADD_U8(BUF, TYPE, VALUE) {BUF[0] = TYPE; BUF[1] = 1; BUF[2] = (VALUE); BUF += 3; }
#define TLV_ADD_U16(BUF, TYPE, VALUE) {BUF[0] = TYPE; BUF[1] = 2; BUF[2] = ((VALUE)&0xFF); BUF[3] = ((VALUE) >> 8)&0xFF; BUF += 4; }
#define SENSOR_TLV_BUFF_MAX                                 (512)

/* public constant prarm */
#define SENSOR_THRESH_CONSTANT_PARAM                        (32)
#define SENSOR_POWER_BACK_CONSTANT_PARAM                    (3)

#define SENSOR_PUBLIC_UPLOAD_SEL_MSK                        PUBLIC_UPLOAD_SEL_ALL

#define SENSOR_DET_RANGE_MAX                                (15000)
#define SENSOR_DET_FSM_PERIOD_MIN                           (20)
#define SENSOR_DET_FRAMES_HOLD_CNT_MIN                      (6)

#define SENSOR_MICRO_EN                                     (BIT(0))
#define SENSOR_MOVE_EN                                      (BIT(2))
#define SENSOR_PRESENCE_EN                                  (BIT(3))
#define SENSOR_EXTERNAL_EN                                  (BIT(4))

#define SENSOR_PRESENCE_DET_MODE_MICRO_TLV                  (BIT(4))
#define SENSOR_PRESENCE_DET_MODE_PRE_TLV                    (BIT(5))

/* public tlv type */
#define SENSOR_PUBLIC_UPLOAD_SEL_TLV                        (0x11)
#define SENSOR_PUBLIC_FORCE_RANG_TLV                        (0x14)
#define SENSOR_POWER_BACK_OFF_TLV                           (0x19)
#define SENSOR_POWER_GAIN_TLV                               (0x19)
#define SENSOR_RANGE_SPEC_THR_TLV                           (0x46)

#define SENSOR_DOUT_MODE_TLV                                (0xA0)
#define SENSOR_DOUT_REPORT_SEL_TLV                          (0xA1)
#define SENSOR_DOUT_REPORT_SEL_MSK                          DOUT_REPORT_SEL_ALL

#define SENSOR_SECTION_SEL_TLV                              (0x20)
#define SENSOR_SECTION_EN_TLV                               (0x21)

#define SENSOR_DET_RANGE_TLV                                (0x24)
#define SENSOR_DET_FSM_PERIOD_TLV                           (0x25)
#define SENSOR_DET_FRAMES_HOLD_CNT_TLV                      (0x26)
#define SENSOR_DET_MODE_SEL_TLV                             (0x28)

/* 251 tlv type */
#define SENSOR_251_WORK_MODE_TLV                            (0x1A)
#define SENSOR_251_LOW_POWER_MICRO_EN_TLV                   (0x28)
#define SENSOR_251_DET_RANGE_TLV                            (0x29)
#define SENSOR_251_LOW_POWER_MICRO_THRESH_TLV               (0x41)
#define SENSOR_251_HIGH_PREFORMANCE_THRESH_TLV              (0x53)
#define SENSOR_251_LOW_POWER_MICRO_FILTER0_TLV              (0x48)
#define SENSOR_251_LOW_POWER_MICRO_FILTER1_TLV              (0x49)
#define SENSOR_251_LOW_POWER_MICRO_FILTER2_TLV              (0x4A)
#define SENSOR_251_HIGH_PREFORMANCE_FILTER0_TLV             (0x59)

/* 251 param config */
#define SENSOR_251_DET_RANGE_0P3M                           (0)
#define SENSOR_251_DET_RANGE_0P5M                           (1)
#define SENSOR_251_DET_RANGE_1M                             (2)
#define SENSOR_251_DET_RANGE_2M                             (3)
#define SENSOR_251_DET_RANGE_3M                             (4)
#define SENSOR_251_DET_RANGE_4M                             (5)
#define SENSOR_251_DET_RANGE_5M                             (6)
#define SENSOR_251_DET_RANGE_6M                             (7)
#define SENSOR_251_DET_RANGE_7M                             (8)
#define SENSOR_251_DET_RANGE_8M                             (9)
#define SENSOR_251_DET_RANGE_9M                             (10)
#define SENSOR_251_DET_RANGE_10M                            (11)
#define SENSOR_251_DET_RANGE_11M                            (12)
#define SENSOR_251_DET_RANGE_12M                            (13)
#define SENSOR_251_DET_RANGE_13M                            (14)
#define SENSOR_251_DET_RANGE_14M                            (15)
#define SENSOR_251_DET_RANGE_15M                            (16)
#define SENSOR_251_DET_RANGE_MAX                            (16)

#define SENSOR_251_WORK_MODE_CFG                            (false)
#define SENSOR_251_MICRO_SENSITIVITY_CFG                    (18)
#define SENSOR_251_MICRO_FILTER_CFG                         (3)
#define SENSOR_251_RESPOND_DELAY_MS_CFG                     (350)
#define SENSOR_251_DET_RANGE_CFG                            (SENSOR_251_DET_RANGE_3M)
#define SENSOR_251_BACK_OFF_CFG                             (0)

/* motion detection tlv type */
#define SENSOR_MICRO_THRESH_TLV                             (0x41)
#define SENSOR_MOVE_THRESH_TLV                              (0x53)

#define SENSOR_MICRO_DET_CAPABILITY_TLV                     (0x44)
#define SENSOR_MOVE_DET_CAPABILITY_TLV                      (0x58)

#define SENSOR_MOVE_DET_LEVEL_TLV                           (0x51)

#define SENSOR_MOVE_TRAC_EN_TLV                             (0x55)
#define SENSOR_MOVE_TRAC_SENSITIVITY_TLV                    (0x56)
#define SENSOR_MOVE_TRAC_LEVEL_TLV                          (0x5A)

/* motion detection param config */

/* presence detection tlv type */
#define SENSOR_PRESENCE_THRESH_TLV                          (0x47)

#define SENSOR_PRESENCE_DET_MODE_TLV                        (0x60)
#define SENSOR_PRESENCE_RESPONE_TIME_TLV                    (0x61)
#define SENSOR_MICRO_SPECTRUM_REPORT_INTERVAL_TLV           (0x62)
#define SENSOR_MICRO_SPECTRUM_CONVERGENCE_FRAMES_TLV        (0x65)

#define SENSOR_EXTERNAL_TYPE_SEL_TLV                        (0x70)
#define SENSOR_EXTERNAL_WKIO_SEL_TLV                        (0x71)
#define SENSOR_EXTERNAL_WKIO_LEVEL_TLV                      (0x72)

/* output tlv type */
#define SENSOR_OUTPUT_SEL_TLV                               (0x30)
#define SENSOR_OUTPUT_EN_TLV                                (0x31)
#define SENSOR_OUTPUT_HOLD_TIME_TLV                         (0x34)
#define SENSOR_OUTPUT_MODE_TLV                              (0x35)
#define SENSOR_OUTPUT_IO_TLV                                (0x36)
#define SENSOR_OUTPUT_NO_TAGET_PRAM_TLV                     (0x37)
#define SENSOR_OUTPUT_HAVE_TAGET_PRAM_TLV                   (0x38)


#define  SENSOR_TARGET_NUM_MAX                      (12)
typedef struct {
	uint16_t target_num;
	uint16_t target_buf[SENSOR_TARGET_NUM_MAX];
} sensor_range_t;
/* firmware download user api as follows */
typedef uint8_t (*DOUT_LEVEL_RD_T)(void);
typedef void (*HIF_RECEIVED_CB_T)(bool msg_err);
typedef int (*HIF_INIT_CB_T)(void);
typedef int (*HIF_WR_CB_T)(uint8_t *pbuff, uint32_t len, uint32_t timeout);
typedef int (*HIF_RD_CB_T)(uint8_t *pbuff, uint32_t len, uint32_t timeout);
typedef int (*SENSOR_TARGET_RANGE_INFO_T)(sensor_range_t *sensor_range, void *user_data);
typedef int (*SENSOR_SYNC_TICK_ERR_T)(void *user_data);
typedef void (*SENSOR_MSG_ERR_CB_T)(void *user_data);
/**
 * @brief Report range spectrum data to application.
 *
 * @param path Represent the specific range spectrum, 1: micro motion 2: presence
 * @param data Pointer to range spectrum data, Q6.
 * @param length The count of range spectrum data.
 * @retval 0 success, else error.
 */
typedef int (*SENSOR_RANGE_SPEC_CB_T)(uint8_t path, uint16_t *data, uint16_t count);

/* sensor info struct */
typedef struct public_det {
    uint16_t range_mm;
    uint16_t period_ms;
    uint16_t det_hold_frames_cnt;
    uint8_t  det_mode;
    uint8_t  reserve[1];
} public_det_t;

typedef struct output_ctrl {
    uint16_t time_ms;
    uint8_t  mode;
    uint8_t  io;
    uint8_t  have_target_pram;
    uint8_t  no_target_pram;
    uint8_t  reserve[2];
} output_ctrl_t;

typedef struct motion_det {
    bool     trac_en;
    uint8_t  capability;
    uint8_t  level;
    uint8_t  trac_level;
    uint16_t sensitivity;
    uint16_t trac_sensitivity;
} motion_det_t;

typedef struct presence_det {
    uint16_t micro_sensitivity;
    uint16_t presence_sensitivity;
    uint8_t  capability;
    uint8_t  det_mode;
    uint8_t  rsp_time;
    uint8_t  micro_spectrum_interval;
    uint8_t  micro_spectrum_convergence_frames;
    uint8_t  external_sel;
    uint8_t  external_io;
    uint8_t  external_level;
} presence_det_t;

typedef struct sensor_public_ctrl {
    uint8_t upload_sel;
    uint8_t force_range_mm;
    uint8_t power_gain_mode;
    uint8_t dout_mode;
    uint8_t dout_report_sel;
    uint8_t reserve[3];
} sensor_public_ctrl_t;

typedef struct sensor_info {
    uint8_t         section_id;
    bool            section_en;
    bool            output_en;
    public_det_t    public_det;
    motion_det_t    motion_det;
    presence_det_t  presence_det;
    output_ctrl_t   output_ctrl;
} sensor_info_t;

typedef enum {
	SENSOR_RANGE_SPEC_MMOTION = 1,
	SENSOR_RANGE_SPEC_PRES,
} sensor_range_spec_path_t;

void sensor_intf_register(HIF_INIT_CB_T init_cb, HIF_WR_CB_T write_cb, HIF_RD_CB_T read_cb, DOUT_LEVEL_RD_T dout_read_cb);

/**
 * @brief register callback to get motion target range detect info.
 *
 * @param report_cb User callback.
 * @param user_data User data.
 * @retval null.
 */
void sensor_range_info_report_register(SENSOR_TARGET_RANGE_INFO_T report_cb, void *user_data);

void sensor_sync_tick_report_register(SENSOR_SYNC_TICK_ERR_T report_cb, void *user_data);
void sensor_msg_err_report_register(SENSOR_MSG_ERR_CB_T report_cb, void *user_data);
void sensor_rs_report_register(SENSOR_RANGE_SPEC_CB_T report_cb);
int sensor_init(void);
int sensor_multi_pram_cfg(void);
int sensor_sync(uint8_t retry_cnt);
int sensor_start_motion_det(void);
int sensor_start_motion_cfg(void);
int sensor_stop_motion_det(void);
int sensor_main_loop_run(bool sync);

int sensor_start(uint32_t on);
int sensor_wakeup(void);
int sensor_suspend(uint32_t pm_type);
int sensor_get_target_info(void);
int sensor_get_rs_micro_info(void);
int sensor_get_rs_presence_info(void);
void sensor_cfg_get(sensor_info_t *info);
void sensor_cfg_set(sensor_info_t *info);
int sensor_wakeup_read_and_suspend(void);
int sensor_read_target_range_info(void);

int sensor_param_send_data(uint8_t *payload, uint16_t length);
int sensor_motion_det_param_config(uint8_t det_mode, uint8_t *tlv, motion_det_t *motion_det_info);
int sensor_presence_det_param_config(uint8_t det_mode, uint8_t *tlv, presence_det_t *presence_det_info);
int sensor_param_config(void);

/**
 * @brief Dump tlv config param info.
 *
 * @param null.
 * @retval null.
 */
void sensor_param_dump(uint8_t *buf, uint32_t size);

/**
 * @brief Config fw_image default pram(image tlv).
 *
 * @param null.
 * @retval 0 success, else error.
 */
int sensor_startup(void);

/**
 * @brief Dynamic pram delivery.
 *
 * @param null.
 * @retval 0 success, else error.
 */
int sensor_pram_cfg_startup(void);
int sensor_public_cfg(uint8_t public_upload_sel, uint8_t dout_mode, uint8_t dout_report_sel);
int sensor_range_cfg(uint8_t cfg_id, uint16_t range_mm);
int sensor_detection_mode_cfg(uint8_t cfg_id, uint8_t det_mode, uint16_t pram, uint16_t extra_pram);
int sensor_period_cfg(uint8_t cfg_id, uint16_t period_ms);
int sensor_set_iic_slave_addr(uint8_t addr);
int sensor_get_sync_tick(void);
int sensor_get_dout_report_sta(void);
sensor_range_t *sensor_get_range_obj(void);

/**
 * @brief read sensor version pram.
 *
 * @param tlv_info.
 * @retval 0 success, else error.
 */
int sensor_image_read_fw_ver(tlv_info_t *tlv_info);

#if SENSOR_MODEL_MRS251 || SENSOR_MODEL_RS2111
int sensor_251_work_mode_cfg(bool high_preformance_mode);
int sensor_251_micro_cfg(uint16_t sensitivity, uint8_t filter);
int sensor_251_det_pram_cfg(uint16_t respond_delay_ms, uint16_t det_range, uint8_t power_back_off);
#endif

/**
 * @brief Set range spectrum bin threshold.
 *
 * @param path Represent the specific range spectrum, 1: micro motion 2: presence
 * @param thr Pointer to the bin threshold of range spectrum, U7Q1.
 * @param count The count of range spectrum bin to be configured.
 * @retval 0 success, else error.
 */
int sensor_range_spec_threshold_cfg(uint8_t path, uint8_t *thr, uint16_t count);

/*	<< porting guide >>
	step 1: move sensor_driver.c and sensor_driver.h into project and modify makefile to build them.
	step 2: modify vendor_porting_layer.c and vendor_porting_layer.c to implement vendor driver and os.
			dependes for different platform.
	step 3: call sensor_intf_register api to register i2c driver or uart dirver, init_cb,write_cb ,read_cb and dout_read_cb should be implement.
	step 4: call sensor_init api to init interface driver and init sensor radar param.
	step 5: call sensor_stop_motion_det api to stop sensor motion sensor detect.
	step 6: call sensor_cfg_get and sensor_cfg_set to modify sensor radar param such as
			1) is_micro set for micro or move detect.
			2) dout_mode set for DOUT status mode or DOUT data mode.
			3) data_mode set for DATA auto upload mode or manual poll mode.
			4) range_mm[0] set for detect range and range_mm[1] set for standby range.
			5) period_ms set for motion detect frame period.
			6) hold_time_ms set for DOUT keep high level for hold time after target dispear.
			   when value 0 will not set into firmware.
			7) micro_det_thresh set for mirco detect sensitivity of mirco moving detect.
			   when value is 0 will not set into firmware.
			8) move_dop_det_thresh set for move dop detect sensitivity of dop moving detect.
			   when value is 0 will not set into firmware.
			9) move_traj_min_trace_len set length for tracing moving target.
			   when value is 0 will not set into firmware.
	step 7: call sensor_start_motion_det api to restart sensor motion sensor detect.
	step 8: call sensor_main_loop_run in main thread wait for dout interrupt to read motion target range data.
	other api instruction as follows:
	1. call sensor_suspend to suspend sensor radar device.
	2. call sensor_wakeup to wakeup sensor radar device.
	3. call sensor_get_target_info to get motion target range data.
	4. call sensor_wakeup_read_and_suspend will first wakeup mmw device and read target range info then set mmw device into sleep.
	5. call sensor_range_info_report_register to report target range info by user callback funtion.
	<<c files introdution>>
	1.sensor_driver.c and sensor_driver.h is the implement to host driver produces not depends on platfrom driver and os.
	2.vendor_porting_layer.c and vendor_porting_layer.h should be implement by vendor hardware platform and os system.
	3.vendor_test_cmd.c is the test cmd use to test sensor_driver api.
	<<points of attention>>
	points 1: after fimware download , mmw device may auto run motion sensor det then stop it before new configure.
*/

#ifdef __cplusplus
}
#endif

#endif /* __FW_DOWNLOAD_H__ */
