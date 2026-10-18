package xiaozhi.modules.agent.service;

import xiaozhi.common.service.BaseService;
import xiaozhi.modules.agent.entity.AgentProactiveEntity;

public interface AgentProactiveService extends BaseService<AgentProactiveEntity> {
    /**
     * 根据智能体ID获取主动提问配置
     * @param agentId 智能体ID
     * @return 主动提问配置实体
     */
    AgentProactiveEntity getByAgentId(String agentId);

    /**
     * 保存或更新主动提问配置
     * @param entity 实体
     */
    void saveOrUpdateByAgentId(AgentProactiveEntity entity);

    /**
     * 根据智能体ID删除主动提问配置
     * @param agentId 智能体ID
     */
    void deleteByAgentId(String agentId);
}
