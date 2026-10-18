package xiaozhi.modules.agent.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;

import org.springframework.stereotype.Service;

import xiaozhi.common.service.impl.BaseServiceImpl;
import xiaozhi.modules.agent.dao.AgentProactiveDao;
import xiaozhi.modules.agent.entity.AgentProactiveEntity;
import xiaozhi.modules.agent.service.AgentProactiveService;

@Service
public class AgentProactiveServiceImpl extends BaseServiceImpl<AgentProactiveDao, AgentProactiveEntity>
        implements AgentProactiveService {

    @Override
    public AgentProactiveEntity getByAgentId(String agentId) {
        return baseDao.selectOne(new QueryWrapper<AgentProactiveEntity>().eq("agent_id", agentId));
    }

    @Override
    public void saveOrUpdateByAgentId(AgentProactiveEntity entity) {
        AgentProactiveEntity exist = getByAgentId(entity.getAgentId());
        if (exist != null) {
            entity.setId(exist.getId());
            updateById(entity);
        } else {
            insert(entity);
        }
    }

    @Override
    public void deleteByAgentId(String agentId) {
        baseDao.delete(new QueryWrapper<AgentProactiveEntity>().eq("agent_id", agentId));
    }
}
