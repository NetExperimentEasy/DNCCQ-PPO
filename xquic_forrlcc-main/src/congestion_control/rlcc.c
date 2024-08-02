/**
 * @copyright Copyright (c) 2022, jinyaoliu
 */

#include "src/congestion_control/rlcc.h"
#include <math.h>
#include "src/common/xqc_time.h"
#include <xquic/xquic.h>
#include <xquic/xquic_typedef.h>
#include "src/congestion_control/xqc_sample.h"
#include "pthread.h"
#include <time.h>
#include <hiredis/hiredis.h>

#define XQC_RLCC_MSS 				XQC_MSS
#define MONITOR_INTERVAL 			100
#define XQC_RLCC_INIT_WIN 			(32 * XQC_RLCC_MSS)
#define XQC_RLCC_INIT_WIN_INT 		32		
#define XQC_RLCC_MIN_WINDOW 		(4 * XQC_RLCC_MSS)
#define XQC_RLCC_MIN_WINDOW_INT 	4
/* when only use pacing_rate, let cwnd bigger than caculated cwnd. */ 
#define CWND_GAIN	 				1.2
#define XQC_RLCC_INF 				0x7fffffff
#define SAMPLE_INTERVAL 			100000 // 100ms
// #define SAMPLE_INTERVAL				1000000		// 1000ms
#define PROBE_INTERVAL 				2000000 // 2s
// #define PROBE_INTERVAL 				10000000 // 10s
#define XQC_DEFAULT_PACING_RATE (((2 * XQC_MSS * 1000000ULL)/(XQC_kInitialRtt * 1000)))

const float xqc_rlcc_init_pacing_gain = 2.885;

static pthread_cond_t cond = PTHREAD_COND_INITIALIZER;
static pthread_mutex_t mutex_lock = PTHREAD_MUTEX_INITIALIZER;

/* satcc action preset data */ 
static int up_actions_list[8] = {30,150,750,3750,18750,93750,468750,2343750};
static int down_actions_list[8] = {1,3,5,9,15,21,33,51};

const uint64_t xqc_pacing_rate_max = (~0) / (uint64_t)MSEC2SEC;
const uint64_t xqc_cwnd_max = (~0) / (uint64_t)MSEC2SEC;

/* see xqc_pacing.c xqc_pacing_rate_calc */
static void
xqc_rlcc_calc_pacing_rate_by_cwnd(xqc_rlcc_t *rlcc)
{	
	xqc_usec_t srtt = rlcc->srtt;
    if (srtt == 0) {
        srtt = XQC_kInitialRtt * 1000;
    }
	rlcc->pacing_rate = (rlcc->cwnd * (uint64_t)MSEC2SEC / srtt);
	rlcc->pacing_rate = xqc_clamp(rlcc->pacing_rate, XQC_DEFAULT_PACING_RATE, xqc_pacing_rate_max);
	return;
}

/* when use pacing_rate action, set matching rate by cwnd */
static void
xqc_rlcc_calc_cwnd_by_pacing_rate(xqc_rlcc_t *rlcc)
{	
	xqc_usec_t srtt = rlcc->srtt;
    if (srtt == 0) {
        srtt = XQC_kInitialRtt * 1000;
    }
	rlcc->cwnd = CWND_GAIN * (rlcc->pacing_rate * srtt / (uint64_t)MSEC2SEC);
	rlcc->cwnd = xqc_clamp(rlcc->cwnd, XQC_RLCC_MIN_WINDOW, xqc_cwnd_max);
	return;
}


/*
 * interface by redis pub/sub
 */
static void
get_redis_conn(xqc_rlcc_t *rlcc)
{	
	rlcc->redis_conn_listener = redisConnect(rlcc->redis_host, rlcc->redis_port);
	rlcc->redis_conn_publisher = redisConnect(rlcc->redis_host, rlcc->redis_port);

	if (!rlcc->redis_conn_listener || !rlcc->redis_conn_publisher)
	{
		printf("redisConnect error\n");
	}
	else if (rlcc->redis_conn_listener->err)
	{
		printf("connection error:%s\n", rlcc->redis_conn_listener->errstr);
		redisFree(rlcc->redis_conn_listener);
	}
	else if (rlcc->redis_conn_publisher->err)
	{
		printf("connection error:%s\n", rlcc->redis_conn_publisher->errstr);
		redisFree(rlcc->redis_conn_publisher);
	}

	return;
}

static void
push_state(redisContext *conn, u_int32_t key, char *value)
{
	/* publish state */
	redisReply *reply;

	reply = redisCommand(conn, "PUBLISH rlccstate_%d %s", key, value);

	if (reply != NULL)
		freeReplyObject(reply);

	return;
}

uint32_t
EMA(uint32_t new, uint32_t old, uint32_t rate) // rate 4, 8
{
	return new/rate + (rate-1)*old/rate;
}

/* get action from redis */
static void
get_result_from_reply(redisReply *reply, xqc_rlcc_t *rlcc)
{
	float cwnd_rate;
	float pacing_rate_rate;
	int cwnd_value;

	int plan = 2;
	/* TODO: use *function to replace plan */

	// plan 1 : control by multiply rate; 
	// plan 2 : control by add rate; owl action space
	// plan 3 : satcc action space old
	// plan 4 : satcc action space new


	if (reply->type == REDIS_REPLY_ARRAY)
	{

		// printf("before cwnd is %d, pacing_rate is %d\n", rlcc->cwnd, rlcc->pacing_rate);

		if (plan==1) {
			// cwnd_rate : [0.5, 3], pacing_rate_rate : [0.5, 3]; if value is 0, means that set it auto
			sscanf(reply->element[2]->str, "%f,%f", &cwnd_rate, &pacing_rate_rate);
			// printf("cwnd_rate %f, pacing_rate_rate:%f, cwnd:%lu, pacing_rate:%lu\n", cwnd_rate, pacing_rate_rate, rlcc->cwnd, rlcc->pacing_rate);
			if (cwnd_rate != 0)
			{
				if (xqc_cwnd_max / cwnd_rate < rlcc->cwnd) // 判断倍率会导致cwnd溢出的情况
				{
					rlcc->cwnd = xqc_cwnd_max - 1;
				}else {
					rlcc->cwnd *= cwnd_rate;
				}
				rlcc->cwnd = xqc_clamp(rlcc->cwnd, XQC_RLCC_MIN_WINDOW, xqc_cwnd_max);
			}

			if (pacing_rate_rate != 0)
			{ // use pacing
				if (xqc_pacing_rate_max / pacing_rate_rate < rlcc->pacing_rate) // 判断倍率会导致速率溢出的情况
				{
					rlcc->pacing_rate = xqc_pacing_rate_max - 1;
				}else {
					rlcc->pacing_rate *= pacing_rate_rate;
				}
				// 上下限约束
				rlcc->pacing_rate = xqc_clamp(rlcc->pacing_rate, XQC_DEFAULT_PACING_RATE, xqc_pacing_rate_max);
			}

			if (cwnd_rate == 0)
			{
				xqc_rlcc_calc_cwnd_by_pacing_rate(rlcc);
			}

			if (pacing_rate_rate == 0)
			{ // use cwnd update pacing_rate
				xqc_rlcc_calc_pacing_rate_by_cwnd(rlcc);
			}
		}
		
		if (plan == 2) {
			// add mode only use cwnd
			// cwnd_value : int , [-n, n]
			int tmp;
			sscanf(reply->element[2]->str, "%d", &cwnd_value);
			tmp = cwnd_value > 0 ? cwnd_value : -cwnd_value;
			if (rlcc->cwnd_int >= tmp || cwnd_value > 0){
				rlcc->cwnd_int += cwnd_value;
			}
			if (rlcc->cwnd_int < XQC_RLCC_MIN_WINDOW_INT)
			{
				rlcc->cwnd_int = XQC_RLCC_MIN_WINDOW_INT; // base cwnd
			}
			rlcc->cwnd = rlcc->cwnd_int * XQC_RLCC_MSS;
			xqc_rlcc_calc_pacing_rate_by_cwnd(rlcc);
		}

		if (plan == 3) {
			// satcc mode also only use cwnd
			// cwnd_value : int , 1:up, -1:down ,0:stay
			sscanf(reply->element[2]->str, "%d", &cwnd_value);
			int a;
			switch (cwnd_value)
			{
			case 1:
				a = up_actions_list[rlcc->up_n] / rlcc->cwnd_int;
				if(a==0) a=1;
				rlcc->cwnd_int = rlcc->cwnd_int + a;

				rlcc->up_times++;
				rlcc->down_times = 0;
				
				// 根据延迟的不同来调节，基础延迟高的话(>=100ms)，连增要求小一点
				int ifup;
				if(rlcc->min_rtt<SAMPLE_INTERVAL){
					ifup = 3;	// 反比例有四次应该足够微增到目标了
				}else{
					ifup = 1;
				}
				if(rlcc->up_times>ifup){	// 连增2次 下次开始加大力度，
										// 连增越多，反比例周期越明显，但起步增速会变差； 连增小的话 反应会快一点
					if(rlcc->up_n<7){
						rlcc->up_n++;
					}
				}

				break;

			case -1:
				if(rlcc->down_times<8){
					if(rlcc->cwnd_int > down_actions_list[rlcc->down_times]){ //防减过猛
						rlcc->cwnd_int -= down_actions_list[rlcc->down_times];
					}
				}else{
					rlcc->cwnd_int -= (rlcc->cwnd_int>>1);
				}

				rlcc->down_times++;
				rlcc->up_times = 0;

				if(rlcc->up_n>0){
					rlcc->up_n--;
				}

				break;

			default:
				if(rlcc->up_n>0){
					rlcc->up_n--;
				}
				break;
			}

			
			if (rlcc->cwnd_int < XQC_RLCC_MIN_WINDOW_INT)
			{
				rlcc->cwnd_int = XQC_RLCC_MIN_WINDOW_INT; // base cwnd
			}

			rlcc->cwnd = rlcc->cwnd_int * XQC_RLCC_MSS;

			xqc_rlcc_calc_pacing_rate_by_cwnd(rlcc);
		}

		if (plan == 4) {
			// [-1, 0, 1]   satcc action new space
			int tmp;
			sscanf(reply->element[2]->str, "%d", &cwnd_value);

			// satcc action
			if (cwnd_value == 0) {
				rlcc->up_stay_EMA = EMA(50000, rlcc->up_stay_EMA, 4);
				rlcc->up_change_EMA = EMA(50000, rlcc->up_change_EMA, 4);
				rlcc->down_stay_EMA = EMA(50000, rlcc->down_stay_EMA, 4);
				rlcc->down_change_EMA = EMA(50000, rlcc->down_change_EMA, 4);
			}else if (cwnd_value == 1) {
				rlcc->up_change_EMA = EMA(100000, rlcc->up_change_EMA, 16);
				rlcc->up_stay_EMA = EMA(2000, rlcc->up_stay_EMA, 16);
				rlcc->down_change_EMA = EMA(50000, rlcc->down_change_EMA, 4);
				cwnd_value = (int)(rlcc->up_change_EMA/rlcc->up_stay_EMA)+1;
			}else if (cwnd_value == -1) {
				rlcc->down_stay_EMA = EMA(2000, rlcc->down_stay_EMA, 16);
                rlcc->down_change_EMA = EMA(100000, rlcc->down_change_EMA, 16);
                rlcc->up_change_EMA = EMA(50000, rlcc->up_change_EMA, 4);
                cwnd_value = -(int)(rlcc->down_change_EMA/rlcc->down_stay_EMA)-1;
			}

			tmp = cwnd_value > 0 ? cwnd_value : -cwnd_value;
			if (rlcc->cwnd_int >= tmp || cwnd_value > 0){
				rlcc->cwnd_int += cwnd_value;
			}
			if (rlcc->cwnd_int < XQC_RLCC_MIN_WINDOW_INT)
			{
				rlcc->cwnd_int = XQC_RLCC_MIN_WINDOW_INT; // base cwnd
			}
			rlcc->cwnd = rlcc->cwnd_int * XQC_RLCC_MSS;
			xqc_rlcc_calc_pacing_rate_by_cwnd(rlcc);
		}

		// printf("after cwnd is %d, pacing_rate is %d\n", rlcc->cwnd, rlcc->pacing_rate);
	}

	return;
}

static void
subscribe(redisContext *conn, xqc_rlcc_t *rlcc)
{
	rlcc->reply = NULL;
	int redis_err = 0;

	if ((rlcc->reply = redisCommand(conn, "SUBSCRIBE rlccaction_%d", rlcc->rlcc_path_flag)) == NULL)
	{
		printf("Failed to Subscibe)\n");
		redisFree(conn);
	}
	else
	{
		freeReplyObject(rlcc->reply);
	}

	return;
}

/* thread function */
static void *
get_action(void *arg)
{
	int redis_err = 0;
	xqc_rlcc_t *rlcc = (xqc_rlcc_t *)arg;
	void *reply = rlcc->reply;
	while (1)
	{
		pthread_mutex_lock(&mutex_lock);
		pthread_cond_wait(&cond, &mutex_lock);
		if ((redis_err = redisGetReply(rlcc->redis_conn_listener, &reply)) == REDIS_OK)
		{
			get_result_from_reply((redisReply *)reply, rlcc);
			freeReplyObject(reply);
		}
		pthread_mutex_unlock(&mutex_lock);
	}
	return 0;
}


/*
 * rlcc
 */

static void
xqc_rlcc_init(void *cong_ctl, xqc_send_ctl_t *ctl_ctx, xqc_cc_params_t cc_params)
{
	xqc_rlcc_t *rlcc = (xqc_rlcc_t *)(cong_ctl);
	memset(rlcc, 0, sizeof(*rlcc));

	rlcc->cwnd = XQC_RLCC_INIT_WIN;
	rlcc->timestamp = xqc_monotonic_timestamp();
	rlcc->rtt = XQC_RLCC_INF;
	rlcc->srtt = 0;	/* let srtt=rtt when srtt==0; sampler's srtt starts with a big value */
	rlcc->lost_interval = 0;
	rlcc->lost = 0;
	rlcc->before_lost = 0;
	rlcc->delivery_rate = 0;
	rlcc->prior_cwnd = rlcc->cwnd;
	rlcc->min_rtt = rlcc->rtt;
	rlcc->is_slow_start = XQC_FALSE;
	rlcc->in_recovery = XQC_FALSE;
	rlcc->throughput = 0;
	rlcc->sent_timestamp = xqc_monotonic_timestamp();
	rlcc->before_total_sent = 0;

	// for satcc action old
	rlcc->cwnd_int = XQC_RLCC_INIT_WIN_INT;
	rlcc->up_n = 0;
	rlcc->down_times = 0;
	rlcc->up_times = 0;

	// for satcc action new
	rlcc->up_change_EMA = 1000; // 0.1
	rlcc->up_stay_EMA = 1000;
	rlcc->down_change_EMA = 1000;
	rlcc->down_stay_EMA = 1000;

	xqc_rlcc_calc_pacing_rate_by_cwnd(rlcc);
	rlcc->prior_pacing_rate = rlcc->pacing_rate;

	if (cc_params.customize_on)
	{
		rlcc->rlcc_path_flag = cc_params.rlcc_path_flag; // 客户端指定flag标识流
		rlcc->redis_host = cc_params.redis_host;
		rlcc->redis_port = cc_params.redis_port;
	}

	get_redis_conn(rlcc);

	if (rlcc->rlcc_path_flag)
	{
		push_state(rlcc->redis_conn_publisher, rlcc->rlcc_path_flag, "state:init");
		subscribe(rlcc->redis_conn_listener, rlcc);
	}
	else
	{
		redisReply *error = redisCommand(rlcc->redis_conn_publisher, "SET error rlcc_path_flag is null");
		freeReplyObject(error);
	}

	/* thread that get action from redis by cond signal */
	pthread_t tid;
	pthread_create(&tid, NULL, get_action, (void *)rlcc);
	pthread_detach(tid);

	return;
}

static void
probe_minrtt(xqc_rlcc_t *rlcc, xqc_sample_t *sampler)
{
	/* update min rtt */
	if (rlcc->min_rtt == 0 || sampler->rtt < rlcc->min_rtt)
	{
		rlcc->min_rtt = sampler->rtt;
		rlcc->min_rtt_timestamp = sampler->now; // min_rtt_timestamp use sampler's now
	}

	/* How to probe */
	/* BBR : cwnd = 4 with 200ms */
	/* 强化学习类算法行为不是绝对稳定，故其无法像xquic bbr那样采用2.5s 75%的方式探索minRTT */
	/* TODO，排队队列预测机制，达到一个阈值就派出那个阈值的数据量来进行min_rtt测量 */
}

static void
xqc_rlcc_on_ack(void *cong_ctl, xqc_sample_t *sampler)
{
	xqc_rlcc_t *rlcc = (xqc_rlcc_t *)(cong_ctl);

	/*	sampler
	 *  prior_delivered : uint64_t : 当前确认的数据包发送前的交付数
	 *	interval : xqc_usec_t : 两次采样的间隔时间，稍大于约1rtt的时间
	 *  delivered : uint32_t : 采样区间内的交付数
	 *  acked : uint32_t : 最新一次被ack的数据的大小
	 *  bytes_inflight : uint32_t : 发送未收到确认的数据量
	 *  prior_inflight : uint32_t : 处理此ack前的inflight
	 *  rtt : xqc_usec_t : 采样区间测得的rtt
	 *  is_app_limited : uint32_t :
	 *  loss : uint32_t : whether packet loss //这个lost可以反映丢包，但是不准确，不适合计算
	 *  total_acked : uint64_t : 总acked数
	 *  srtt : xqc_usec_t
	 *  delivery_rate : uint32_t : (uint64_t)(1e6 * sampler->delivered / sampler->interval);
	 *  prior_lost : uint32_t : bbr2用于判断丢包是否过快, 此包发送前的丢包数  但是这个丢包数很诡异，应该是减去了已经重传的包
	 *  tx_in_flight ： 此包发送时的inflight（包括此包）
	 *  lost_pkts : uint32 : bbr2用于判断丢包是否过快，目前为止的丢包总数-此包发送前的丢包数
	 *     一种计算采样周期丢包率的方法：
	 * 			记录lost_pkts差（lost_interval），除以此周期的发包数
	 * 	TODO:	目前为之的丢包总数 - 上个周期的丢包总数 来作为此周期的丢包书
	 * 
	 *  total_sent  ctl->ctl_bytes_send
	 */

	// printf("debug:pd:%ld, i:%ld, d:%d, a:%d, bi:%d, pi:%d, r:%ld, ial:%d, l:%d, ta:%ld, s:%ld, dr:%d, pl:%d, lp:%d\n",
	// 	   sampler->prior_delivered,
	// 	   sampler->interval,
	// 	   sampler->delivered,
	// 	   sampler->acked,
	// 	   sampler->bytes_inflight,
	// 	   sampler->prior_inflight,
	// 	   sampler->rtt,
	// 	   sampler->is_app_limited,
	// 	   sampler->loss,
	// 	   sampler->total_acked,
	// 	   sampler->srtt,
	// 	   sampler->delivery_rate,
	// 	   sampler->prior_lost,
	// 	   sampler->lost_pkts);

	xqc_usec_t current_time = xqc_monotonic_timestamp();

	probe_minrtt(rlcc, sampler);

	int plan = 2; // plan 1 100ms; plan 2 minrtt+100；plan 3 double rtt sample

	/* TODO: use *function to replace plan */

	if (plan == 1)
	{
		/* plan1. 100ms fixed monitor interval (get data from xqc_sampler) */ 
		// if (rlcc->timestamp + SAMPLE_INTERVAL <= current_time) // 100ms
		// if (rlcc->timestamp + (SAMPLE_INTERVAL/2) <= current_time)  // 50ms
		if (rlcc->timestamp + rlcc->min_rtt <= current_time)  // 1 minrtt
		{ // 100000 100ms

			rlcc->timestamp = current_time; // 更新时间戳
			uint32_t sent_interval = sampler->send_ctl->ctl_bytes_send - rlcc->before_total_sent;
			rlcc->throughput = 1e6 * sent_interval / (current_time - rlcc->sent_timestamp);
			rlcc->sent_timestamp = current_time;
			rlcc->before_total_sent = sampler->send_ctl->ctl_bytes_send;
			
			rlcc->lost_interval = sampler->lost_pkts - rlcc->before_lost;
			rlcc->lost_interval = xqc_max(rlcc->lost_interval, 0);  // <0 : not lost
			rlcc->before_lost = sampler->lost_pkts;

			if (rlcc->rlcc_path_flag)
			{	
				uint32_t cwnd = rlcc->cwnd >> 10;
				uint32_t pacing_rate = rlcc->pacing_rate >> 10;
				char value[500] = {0};
				sprintf(value, "%d;%d;%ld;%ld;%ld;%d;%d;%d;%d;%d;%d;%d",
						cwnd,
						pacing_rate,
						sampler->rtt,
						rlcc->min_rtt,
						sampler->srtt,
						sampler->bytes_inflight,
						rlcc->lost_interval,
						sampler->lost_pkts,
						sampler->is_app_limited,
						sampler->delivery_rate,
						rlcc->throughput, // delivery_rate 与 throughput 不作为状态，作为单独的奖励计算使用
						sent_interval);
				push_state(rlcc->redis_conn_publisher, rlcc->rlcc_path_flag, value);
				pthread_mutex_lock(&mutex_lock);
				// send signal
				pthread_cond_signal(&cond);
				pthread_mutex_unlock(&mutex_lock);
			}
			else
			{
				redisReply *error = redisCommand(rlcc->redis_conn_publisher, "SET error rlcc_path_flag is null");
				freeReplyObject(error);
			}
		}
	}

	if (plan == 2)
	{
		// plan2. minrtt+100ms sample method
		// xqc_usec_t time_interval;

		if (rlcc->sample_start > current_time)
		{
			// before sample
			rlcc->rtt = sampler->rtt;
			rlcc->srtt = rlcc->rtt; /* starts with rtt, then update with sampler's srtt */
			rlcc->inflight = sampler->bytes_inflight;
			rlcc->lost = sampler->lost_pkts;
			rlcc->delivery_rate = sampler->delivery_rate;
			
			rlcc->before_total_sent = sampler->send_ctl->ctl_bytes_send;
			rlcc->sent_timestamp = current_time;

			rlcc->before_lost = sampler->lost_pkts;
		}

		if (rlcc->sample_start <= current_time)
		{
			// sample
			rlcc->rtt -= rlcc->rtt >> 2;
			rlcc->rtt += (sampler->rtt >> 2);

			rlcc->srtt -= rlcc->srtt >> 2;
			rlcc->srtt += (sampler->srtt >> 2);

			rlcc->inflight -= rlcc->inflight >> 2;
			rlcc->inflight += (sampler->bytes_inflight >> 2);

			// printf("rlcc lost %d, >>2 %d", rlcc->lost, rlcc->lost >> 2);
			rlcc->lost -= rlcc->lost >> 2;
			rlcc->lost += (sampler->lost_pkts >> 2);
			// printf("rlcc lost after %d", rlcc->lost);

			rlcc->delivery_rate -= rlcc->delivery_rate >> 2;
			rlcc->delivery_rate += (sampler->delivery_rate >> 2);
		}

		if (rlcc->sample_stop <= current_time)
		{
			// stop sample and send signal

			rlcc->timestamp = current_time;
			rlcc->sample_start = current_time + rlcc->min_rtt;
			rlcc->sample_stop = rlcc->sample_start + xqc_min(rlcc->min_rtt, SAMPLE_INTERVAL);
			
			uint32_t sent_interval = sampler->send_ctl->ctl_bytes_send - rlcc->before_total_sent;
			rlcc->throughput = 1e6 * sent_interval / (current_time - rlcc->sent_timestamp);
			
			rlcc->lost_interval = sampler->lost_pkts - rlcc->before_lost;
			rlcc->lost_interval = xqc_max(rlcc->lost_interval, 0);  // <0 : not lost

			if (rlcc->rlcc_path_flag)
			{	
				uint32_t cwnd = rlcc->cwnd >> 10; /* TODO, uint64 >> 10 may overflow (rlccenv recv type is float32) */
				uint32_t pacing_rate = rlcc->pacing_rate >> 10;
				char value[500] = {0};
				sprintf(value, "%d;%d;%ld;%ld;%ld;%d;%d;%d;%d;%d;%d;%d",
						cwnd,		
						pacing_rate,
						rlcc->rtt,
						rlcc->min_rtt,
						rlcc->srtt,
						rlcc->inflight,
						rlcc->lost_interval,
						rlcc->lost,
						sampler->is_app_limited,
						rlcc->delivery_rate,     // notice:此处是采样周期内平滑后的delivery_rate
						rlcc->throughput,
						sent_interval);
				push_state(rlcc->redis_conn_publisher, rlcc->rlcc_path_flag, value);
				pthread_mutex_lock(&mutex_lock);
				// send signal
				pthread_cond_signal(&cond);
				pthread_mutex_unlock(&mutex_lock);
			}
			else
			{
				redisReply *error = redisCommand(rlcc->redis_conn_publisher, "SET error rlcc_path_flag is null");
				freeReplyObject(error);
			}
		}
	}

	if (plan == 3)
	{
		// plan3. double rtt sample method
		// xqc_usec_t time_interval;

		if (rlcc->sample_start > current_time)
		{
			// before sample
			rlcc->rtt = sampler->rtt;
			rlcc->srtt = rlcc->rtt; /* starts with rtt, then update with sampler's srtt */
			rlcc->inflight = sampler->bytes_inflight;
			rlcc->lost = sampler->lost_pkts;
			rlcc->delivery_rate = sampler->delivery_rate;
			
			rlcc->before_total_sent = sampler->send_ctl->ctl_bytes_send;
			rlcc->sent_timestamp = current_time;

			rlcc->before_lost = sampler->lost_pkts;
		}

		if (rlcc->sample_start <= current_time)
		{
			// sample
			rlcc->rtt -= rlcc->rtt >> 2;
			rlcc->rtt += (sampler->rtt >> 2);

			rlcc->srtt -= rlcc->srtt >> 2;
			rlcc->srtt += (sampler->srtt >> 2);

			rlcc->inflight -= rlcc->inflight >> 2;
			rlcc->inflight += (sampler->bytes_inflight >> 2);

			// printf("rlcc lost %d, >>2 %d", rlcc->lost, rlcc->lost >> 2);
			rlcc->lost -= rlcc->lost >> 2;
			rlcc->lost += (sampler->lost_pkts >> 2);
			// printf("rlcc lost after %d", rlcc->lost);

			rlcc->delivery_rate -= rlcc->delivery_rate >> 2;
			rlcc->delivery_rate += (sampler->delivery_rate >> 2);
		}

		if (rlcc->sample_stop <= current_time)
		{
			// stop sample and send signal

			rlcc->timestamp = current_time;
			rlcc->sample_start = current_time + rlcc->min_rtt;
			rlcc->sample_stop = rlcc->sample_start + rlcc->min_rtt; // double minRTT
			
			uint32_t sent_interval = sampler->send_ctl->ctl_bytes_send - rlcc->before_total_sent;
			rlcc->throughput = 1e6 * sent_interval / (current_time - rlcc->sent_timestamp);
			
			rlcc->lost_interval = sampler->lost_pkts - rlcc->before_lost;
			rlcc->lost_interval = xqc_max(rlcc->lost_interval, 0);  // <0 : not lost

			if (rlcc->rlcc_path_flag)
			{	
				uint32_t cwnd = rlcc->cwnd >> 10; /* TODO, uint64 >> 10 may overflow (rlccenv recv type is float32) */
				uint32_t pacing_rate = rlcc->pacing_rate >> 10;
				char value[500] = {0};
				sprintf(value, "%d;%d;%ld;%ld;%ld;%d;%d;%d;%d;%d;%d;%d",
						cwnd,		
						pacing_rate,
						rlcc->rtt,
						rlcc->min_rtt,
						rlcc->srtt,
						rlcc->inflight,
						rlcc->lost_interval,
						rlcc->lost,
						sampler->is_app_limited,
						rlcc->delivery_rate,     // notice:此处是采样周期内平滑后的delivery_rate
						rlcc->throughput,
						sent_interval);
				push_state(rlcc->redis_conn_publisher, rlcc->rlcc_path_flag, value);
				pthread_mutex_lock(&mutex_lock);
				// send signal
				pthread_cond_signal(&cond);
				pthread_mutex_unlock(&mutex_lock);
			}
			else
			{
				redisReply *error = redisCommand(rlcc->redis_conn_publisher, "SET error rlcc_path_flag is null");
				freeReplyObject(error);
			}
		}
	}
	return;
}

/*
 * Other functions
 */

static void
xqc_rlcc_on_lost(void *cong_ctl, xqc_usec_t lost_sent_time)
{
	// xqc_rlcc_t *rlcc = (xqc_rlcc_t *)(cong_ctl);
	// xqc_usec_t current_time = xqc_monotonic_timestamp();
	return;
}

static uint64_t
xqc_rlcc_get_cwnd(void *cong_ctl)
{
	xqc_rlcc_t *rlcc = (xqc_rlcc_t *)(cong_ctl);
	return rlcc->cwnd;
}

static void
xqc_rlcc_reset_cwnd(void *cong_ctl)
{
	xqc_rlcc_t *rlcc = (xqc_rlcc_t *)(cong_ctl);
	rlcc->cwnd = XQC_RLCC_MIN_WINDOW;
	rlcc->cwnd_int = XQC_RLCC_MIN_WINDOW_INT;
	xqc_rlcc_calc_pacing_rate_by_cwnd(rlcc);
	return;
}

size_t
xqc_rlcc_size()
{
	return sizeof(xqc_rlcc_t);
}

static uint32_t
xqc_rlcc_get_pacing_rate(void *cong_ctl)
{
	xqc_rlcc_t *rlcc = (xqc_rlcc_t *)(cong_ctl);
	return rlcc->pacing_rate;
}

static void
xqc_rlcc_restart_from_idle(void *cong_ctl, uint64_t conn_delivered)
{	
	/* will be called when ctl->ctl_bytes_in_flight == 0 */
	/* current do nothing */ 
	return;
}

static int
xqc_rlcc_in_recovery(void *cong)
{
	xqc_rlcc_t *rlcc = (xqc_rlcc_t *)(cong);
	return rlcc->in_recovery; /* never in recovery, all control by reinforcement learning */ 
}

const xqc_cong_ctrl_callback_t xqc_rlcc_cb = {
	.xqc_cong_ctl_size = xqc_rlcc_size,
	.xqc_cong_ctl_init = xqc_rlcc_init,
	.xqc_cong_ctl_on_lost = xqc_rlcc_on_lost,
	.xqc_cong_ctl_on_ack_multiple_pkts = xqc_rlcc_on_ack, // bind with change pacing rate
	// .xqc_cong_ctl_on_ack				= xqc_rlcc_on_ack,	// only change cwnd
	.xqc_cong_ctl_get_cwnd = xqc_rlcc_get_cwnd,
	.xqc_cong_ctl_get_pacing_rate = xqc_rlcc_get_pacing_rate,
	.xqc_cong_ctl_reset_cwnd = xqc_rlcc_reset_cwnd,
	.xqc_cong_ctl_restart_from_idle = xqc_rlcc_restart_from_idle,
	.xqc_cong_ctl_in_recovery = xqc_rlcc_in_recovery,
};
