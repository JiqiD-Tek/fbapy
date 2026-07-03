CREATE TABLE `u_bill_account` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `subject_type` VARCHAR(16) NOT NULL COMMENT 'USER / DEVICE',
  `subject_key` VARCHAR(64) NOT NULL COMMENT '用户 ID 或设备 DID',
  `balance_token` BIGINT NOT NULL DEFAULT 0 COMMENT '当前余额快照，单位 token',
  `status` VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' COMMENT 'ACTIVE / BLOCKED',
  `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_subject` (`subject_type`, `subject_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='计费主体';


CREATE TABLE `u_bill_session` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `session_id` VARCHAR(64) NOT NULL COMMENT 'xiaozhi-server session_id',
  `account_id` BIGINT UNSIGNED NOT NULL COMMENT '计费主体 ID',
  `device_did` VARCHAR(64) NOT NULL COMMENT '设备 DID',
  `started_at` DATETIME NOT NULL COMMENT '会话开始时间',
  `status` VARCHAR(16) NOT NULL DEFAULT 'OPEN' COMMENT 'OPEN / BLOCKED / CLOSED / ABORTED',
  `last_activity_at` DATETIME DEFAULT NULL COMMENT '最近活跃时间',
  `ended_at` DATETIME DEFAULT NULL COMMENT '会话结束时间',
  `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session_id` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实时计费会话';


CREATE TABLE `u_bill_txn` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `charge_id` VARCHAR(64) NOT NULL COMMENT '账务业务号，当前 DEBIT 场景等于 usage_id',
  `account_id` BIGINT UNSIGNED NOT NULL COMMENT '计费主体 ID',
  `change_type` VARCHAR(16) NOT NULL COMMENT 'DEBIT / RECHARGE / REFUND / ADJUST',
  `delta_token` BIGINT NOT NULL COMMENT '余额变动，正数加款，负数扣款',
  `balance_after_token` BIGINT NOT NULL COMMENT '变动后余额快照',
  `account_status_after` VARCHAR(16) NOT NULL COMMENT '入账后账户状态',
  `session_status_after` VARCHAR(16) NOT NULL COMMENT '入账后会话状态',
  `usage_id` VARCHAR(64) DEFAULT NULL COMMENT '来源 usage ID，DEBIT 场景必填',
  `session_id` VARCHAR(64) DEFAULT NULL COMMENT '来源会话 ID',
  `turn_no` INT DEFAULT NULL COMMENT '来源回合号',
  `stage_no` INT DEFAULT NULL COMMENT '来源阶段号',
  `usage_kind` VARCHAR(16) DEFAULT NULL COMMENT 'ASR / LLM_INPUT / LLM_OUTPUT / TTS',
  `usage_token` BIGINT DEFAULT NULL COMMENT '本次 usage 已换算好的 token',
  `provider` VARCHAR(64) DEFAULT NULL COMMENT '来源 provider',
  `occurred_at` DATETIME DEFAULT NULL COMMENT '发生时间',
  `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_txn_usage_id` (`usage_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账务流水';
