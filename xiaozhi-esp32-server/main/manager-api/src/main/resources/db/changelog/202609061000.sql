-- liquibase formatted sql

-- changeset xiaozhi:202609061000
CREATE TABLE ai_agent_proactive (
    id VARCHAR(32) NOT NULL COMMENT '主键',
    agent_id VARCHAR(32) NOT NULL COMMENT '智能体ID',
    proactive JSON COMMENT '主动提问配置：{"enabled":bool,"start_time":"HH:MM","end_time":"HH:MM","interval":int,"script":"str","weekdays":[1-7]}',
    creator BIGINT COMMENT '创建者',
    created_at DATETIME COMMENT '创建时间',
    updater BIGINT COMMENT '更新者',
    updated_at DATETIME COMMENT '更新时间',
    PRIMARY KEY (id),
    INDEX idx_agent_id (agent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='智能体主动提问配置表';
