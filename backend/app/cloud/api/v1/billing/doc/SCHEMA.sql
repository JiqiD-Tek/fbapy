CREATE TABLE `u_bill_account` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `subject_type` VARCHAR(16) NOT NULL COMMENT '计费主体类型，当前主路径固定为 DEVICE，保留 USER 扩展位',
  `subject_key` VARCHAR(64) NOT NULL COMMENT '计费主体标识，DEVICE 场景下通常等于 device_did',
  `balance_token` BIGINT NOT NULL DEFAULT 0 COMMENT '当前余额快照，单位 token',
  `status` VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' COMMENT '账户状态：ACTIVE / BLOCKED',
  `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_subject` (`subject_type`, `subject_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='计费账户';


CREATE TABLE `u_bill_session` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `session_id` VARCHAR(64) NOT NULL COMMENT 'xiaozhi-server session_id',
  `account_id` BIGINT UNSIGNED NOT NULL COMMENT '所属计费账户 ID',
  `device_did` VARCHAR(64) NOT NULL COMMENT '设备 DID',
  `started_at` DATETIME NOT NULL COMMENT '会话开始时间',
  `status` VARCHAR(16) NOT NULL DEFAULT 'OPEN' COMMENT '会话状态：OPEN / BLOCKED / CLOSED / ABORTED',
  `last_activity_at` DATETIME NULL DEFAULT NULL COMMENT '最近活跃时间',
  `ended_at` DATETIME NULL DEFAULT NULL COMMENT '会话结束时间',
  `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session_id` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实时计费会话';


CREATE TABLE `u_bill_txn` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `usage_id` VARCHAR(128) NOT NULL COMMENT 'Turn 级幂等 ID，推荐格式 session_id:turn_no:TURN',
  `account_id` BIGINT UNSIGNED NOT NULL COMMENT '所属计费账户 ID',
  `session_id` VARCHAR(64) NOT NULL COMMENT '来源会话 ID',
  `turn_no` INT NOT NULL COMMENT '来源回合号',
  `change_type` VARCHAR(16) NOT NULL DEFAULT 'DEBIT' COMMENT '变动类型，当前固定写 DEBIT',
  `usage_token` BIGINT NOT NULL COMMENT '本次 Turn 汇总消耗，来源于上游 Metering',
  `delta_token` BIGINT NOT NULL COMMENT '余额变动值，DEBIT 场景下为负数',
  `balance_after_token` BIGINT NOT NULL COMMENT '变动后余额快照',
  `account_status_after` VARCHAR(16) NOT NULL COMMENT '入账后账户状态',
  `session_status_after` VARCHAR(16) NOT NULL COMMENT '入账后会话状态',
  `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入账时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_txn_usage_id` (`usage_id`),
  KEY `idx_account_created_time` (`account_id`, `created_time`),
  KEY `idx_session_turn` (`session_id`, `turn_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账务流水';
