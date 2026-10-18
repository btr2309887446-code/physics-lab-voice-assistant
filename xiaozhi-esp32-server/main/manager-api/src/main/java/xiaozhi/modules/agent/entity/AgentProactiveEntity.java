package xiaozhi.modules.agent.entity;

import java.util.Date;
import java.util.Map;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@TableName(value = "ai_agent_proactive", autoResultMap = true)
@Schema(description = "智能体主动提问配置")
public class AgentProactiveEntity {

    @TableId(type = IdType.ASSIGN_UUID)
    @Schema(description = "主键")
    private String id;

    @Schema(description = "智能体ID")
    private String agentId;

    @Schema(description = "主动提问配置")
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> proactive;

    @Schema(description = "创建者")
    private Long creator;

    @Schema(description = "创建时间")
    private Date createdAt;

    @Schema(description = "更新者")
    private Long updater;

    @Schema(description = "更新时间")
    private Date updatedAt;
}
