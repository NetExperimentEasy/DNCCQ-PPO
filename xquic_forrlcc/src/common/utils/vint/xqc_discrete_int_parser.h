/**
 * @copyright Copyright (c) 2022, Alibaba Group Holding Limited
 */

#ifndef _XQC_DISCRETE_INT_PARSER_H_
#define _XQC_DISCRETE_INT_PARSER_H_

#include "include/xquic/xquic_typedef.h"
#include "xqc_variable_len_int.h"
#include "src/common/xqc_config.h"
#include "src/common/xqc_common.h"
#include <sys/types.h>

/* state for parsing discrete int */
typedef struct {
    uint64_t    vi;     /* temporary or final value */
    size_t      left;   /* bytes needs to be read to finish the discrete int */
} xqc_discrete_int_pctx_t;


/**
 * @brief reset parse context
 */
void xqc_discrete_int_pctx_clear(xqc_discrete_int_pctx_t *pctx);

/**
 * @brief parse vint from buffers which might be truncated
 * @param p:    input buffer
 * @param sz:   buffer size
 * @param st:   parse state
 * @param fin:  output for parse finished
 */
ssize_t xqc_discrete_vint_parse(const uint8_t *p, size_t sz,
    xqc_discrete_int_pctx_t *pctx, xqc_bool_t *fin);

/**
 * @brief parse fixed len int from buffers which might be truncated
 */
ssize_t xqc_fixed_len_int_parse(const uint8_t *p, size_t sz, uint8_t len,
    xqc_discrete_int_pctx_t *pctx, xqc_bool_t *fin);

#endif