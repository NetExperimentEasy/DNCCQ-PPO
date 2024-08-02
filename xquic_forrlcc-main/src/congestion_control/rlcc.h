/**
 * @copyright Copyright (c) 2022, jinyaoliu 
 */

#ifndef _RLCC_CC_H_INCLUDED_
#define _RLCC_CC_H_INCLUDED_

#include <xquic/xquic_typedef.h>
#include <xquic/xquic.h>
#include "src/transport/xqc_send_ctl.h"
#include "src/transport/xqc_packet_out.h"
#include <hiredis/hiredis.h>  

#define MSEC2SEC 1000000

typedef struct xqc_rlcc_s {
    uint64_t                cwnd;
    /* Current pacing rate */
    uint64_t                pacing_rate;
    redisContext*           redis_conn_listener;
    redisContext*           redis_conn_publisher;
    void*                   reply; // subscribe
    char*                   redis_host;
    uint32_t                redis_port;

    /* sample state */
    xqc_usec_t              timestamp;
    xqc_usec_t              sample_start;   // 双rtt采样法的采样起止时间，更新timestamp时，更新这两个时间
    xqc_usec_t              sample_stop;
    xqc_usec_t              rtt;
    xqc_usec_t              srtt;           /* rlcc->srtt is the srtt of sample interval */
    int32_t                 lost_interval;   // 记录采样状态周期内出现的丢包数
    uint32_t                lost;       // 双rtt方案，平滑lost ：lost_pkts
    uint32_t                before_lost;    // lost_pkts的记录点，用于计算lost_interval
    uint32_t                delivery_rate;
    uint32_t                inflight;
    uint64_t                prior_cwnd;
    uint64_t                prior_pacing_rate;
    xqc_usec_t              min_rtt;
    xqc_usec_t              min_rtt_timestamp;

    xqc_bool_t              in_recovery;
    xqc_bool_t              is_slow_start;

    // rlcc_flag : for mininet env
    uint32_t                rlcc_path_flag;

    // satcc action old space plan3
    uint32_t                cwnd_int;
    uint8_t                 up_times;
    uint8_t                 down_times;
    uint8_t                 up_n;

    // satcc action new space plan4
    uint32_t                up_change_EMA;
	uint32_t                up_stay_EMA;
	uint32_t                down_change_EMA;
	uint32_t                down_stay_EMA;

    // cacu throughput by total_sent
    uint64_t                before_total_sent;
    xqc_usec_t              sent_timestamp;
    uint32_t                throughput;

} xqc_rlcc_t;

extern const xqc_cong_ctrl_callback_t xqc_rlcc_cb;

#endif /* _XQC_RLCC_H_INCLUDED_ */