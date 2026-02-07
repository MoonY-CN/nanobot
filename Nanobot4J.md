# Nanobot4J - Spring AI Alibaba 实现方案

## 概述

本文档描述如何使用 **Spring AI Alibaba 1.1.2.0** 实现 nanobot 的完整功能。nanobot 是一个超轻量级个人 AI 助手，Java 版本将提供更强大的类型安全、更好的并发性能和更成熟的企业级支持。

## 技术栈

- **Java 21+** - 使用 Virtual Threads 简化异步编程
- **Spring Boot 3.2+** - 基础框架
- **Spring AI Alibaba 1.1.2.0** - AI 核心能力
- **Spring WebFlux** - 响应式 HTTP 客户端
- **Spring WebSocket** - WebSocket 支持
- **Quartz Scheduler** - 定时任务
- **Jackson** - JSON 处理

## 项目架构

```
nanobot-java/
├── src/main/java/com/nanobot/
│   ├── NanobotApplication.java
│   ├── config/                    # 配置类
│   │   ├── NanobotProperties.java
│   │   └── WebSocketConfig.java
│   ├── agent/                     # Agent 核心
│   │   ├── AgentService.java
│   │   ├── ToolCallingService.java
│   │   └── context/               # 上下文构建
│   │       ├── ContextBuilder.java
│   │       └── PromptTemplate.java
│   ├── tools/                     # 工具系统
│   │   ├── Tool.java
│   │   ├── ToolRegistry.java
│   │   ├── ToolResult.java
│   │   └── impl/                  # 工具实现
│   │       ├── FileSystemTool.java
│   │       ├── ShellTool.java
│   │       ├── WebSearchTool.java
│   │       ├── MessageTool.java
│   │       ├── SpawnTool.java
│   │       └── CronTool.java
│   ├── channels/                  # 频道系统
│   │   ├── Channel.java
│   │   ├── ChannelManager.java
│   │   └── impl/
│   │       ├── TelegramChannel.java
│   │       ├── DiscordChannel.java
│   │       └── CliChannel.java
│   ├── memory/                    # 记忆系统
│   │   ├── MemoryService.java
│   │   └── SessionManager.java
│   ├── cron/                      # 定时任务
│   │   ├── CronService.java
│   │   └── JobRepository.java
│   └── bus/                       # 消息总线
│       ├── MessageBus.java
│       └── events/
├── src/main/resources/
│   ├── application.yml
│   └── prompts/
│       ├── system.st              # 系统提示词模板
│       └── agent.st               # Agent 提示词模板
└── pom.xml
```

## Maven 依赖

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
        <relativePath/>
    </parent>
    
    <groupId>com.nanobot</groupId>
    <artifactId>nanobot-java</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    
    <properties>
        <java.version>21</java.version>
        <spring-ai-alibaba.version>1.1.2.0</spring-ai-alibaba.version>
    </properties>
    
    <dependencies>
        <!-- Spring Boot 基础 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-websocket</artifactId>
        </dependency>
        
        <!-- Spring AI Alibaba -->
        <dependency>
            <groupId>com.alibaba.cloud.ai</groupId>
            <artifactId>spring-ai-alibaba-starter</artifactId>
            <version>${spring-ai-alibaba.version}</version>
        </dependency>
        
        <!-- 工具调用支持 -->
        <dependency>
            <groupId>com.alibaba.cloud.ai</groupId>
            <artifactId>spring-ai-alibaba-tool-calling</artifactId>
            <version>${spring-ai-alibaba.version}</version>
        </dependency>
        
        <!-- 定时任务 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-quartz</artifactId>
        </dependency>
        
        <!-- JSON 处理 -->
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
        </dependency>
        
        <!-- HTTP 客户端 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-webflux</artifactId>
        </dependency>
        
        <!-- 工具库 -->
        <dependency>
            <groupId>org.apache.commons</groupId>
            <artifactId>commons-lang3</artifactId>
        </dependency>
        
        <!-- 测试 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

## 核心实现

### 1. 主应用类

```java
package com.nanobot;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableAsync
@EnableScheduling
public class NanobotApplication {
    public static void main(String[] args) {
        SpringApplication.run(NanobotApplication.class, args);
    }
}
```

### 2. 配置类

```java
package com.nanobot.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.List;

@Data
@Component
@ConfigurationProperties(prefix = "nanobot")
public class NanobotProperties {
    
    private String workspacePath;
    private AgentConfig agent = new AgentConfig();
    private ChannelsConfig channels = new ChannelsConfig();
    private ToolsConfig tools = new ToolsConfig();
    
    @Data
    public static class AgentConfig {
        private String model = "qwen-turbo";
        private int maxToolIterations = 10;
        private int contextWindow = 10;
    }
    
    @Data
    public static class ChannelsConfig {
        private TelegramConfig telegram = new TelegramConfig();
        private DiscordConfig discord = new DiscordConfig();
        
        @Data
        public static class TelegramConfig {
            private boolean enabled = false;
            private String token;
        }
        
        @Data
        public static class DiscordConfig {
            private boolean enabled = false;
            private String token;
        }
    }
    
    @Data
    public static class ToolsConfig {
        private boolean restrictToWorkspace = true;
        private ShellConfig shell = new ShellConfig();
        private WebConfig web = new WebConfig();
        
        @Data
        public static class ShellConfig {
            private int timeout = 60;
            private List<String> denyPatterns;
        }
        
        @Data
        public static class WebConfig {
            private String searchApiKey;
        }
    }
}
```

### 3. 工具系统

#### 3.1 工具接口

```java
package com.nanobot.tools;

import com.fasterxml.jackson.databind.JsonNode;
import lombok.Data;

/**
 * 工具接口 - 所有工具必须实现
 */
public interface Tool {
    
    /**
     * 获取工具名称
     */
    String getName();
    
    /**
     * 获取工具描述（用于 LLM 理解）
     */
    String getDescription();
    
    /**
     * 获取工具参数模式（JSON Schema）
     */
    JsonNode getParametersSchema();
    
    /**
     * 执行工具
     */
    ToolResult execute(ToolParameters parameters);
    
    /**
     * 检查工具是否可用
     */
    default boolean isAvailable() {
        return true;
    }
}
```

#### 3.2 工具参数

```java
package com.nanobot.tools;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

/**
 * 工具参数
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ToolParameters {
    private String action;
    private Map<String, Object> parameters;
}
```

#### 3.3 工具结果

```java
package com.nanobot.tools;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 工具执行结果
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ToolResult {
    private boolean success;
    private String output;
    private String error;
    
    public static ToolResult success(String output) {
        return new ToolResult(true, output, null);
    }
    
    public static ToolResult failure(String error) {
        return new ToolResult(false, null, error);
    }
}
```

#### 3.4 工具注册表

```java
package com.nanobot.tools;

import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Collection;
import java.util.HashMap;
import java.util.Map;

/**
 * 工具注册表 - 管理所有可用工具
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ToolRegistry {
    
    private final Map<String, Tool> tools = new HashMap<>();
    private final Collection<Tool> toolBeans;
    
    @PostConstruct
    public void init() {
        // 自动注册所有 Tool 类型的 Bean
        for (Tool tool : toolBeans) {
            register(tool);
        }
        log.info("已注册 {} 个工具", tools.size());
    }
    
    public void register(Tool tool) {
        if (!tool.isAvailable()) {
            log.warn("工具 {} 不可用，跳过注册", tool.getName());
            return;
        }
        tools.put(tool.getName(), tool);
        log.info("注册工具: {}", tool.getName());
    }
    
    public Tool getTool(String name) {
        return tools.get(name);
    }
    
    public Collection<Tool> getAllTools() {
        return tools.values();
    }
    
    public boolean hasTool(String name) {
        return tools.containsKey(name);
    }
}
```

### 4. 文件系统工具实现

```java
package com.nanobot.tools.impl;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanobot.config.NanobotProperties;
import com.nanobot.tools.Tool;
import com.nanobot.tools.ToolParameters;
import com.nanobot.tools.ToolResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;

/**
 * 文件系统工具 - 读写文件、列出目录
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class FileSystemTool implements Tool {
    
    private final NanobotProperties properties;
    private final ObjectMapper objectMapper;
    
    @Override
    public String getName() {
        return "filesystem";
    }
    
    @Override
    public String getDescription() {
        return """
            文件系统操作工具。支持的操作：
            - read: 读取文件内容
            - write: 写入文件内容
            - list: 列出目录内容
            - edit: 编辑文件（搜索替换）
            """;
    }
    
    @Override
    public JsonNode getParametersSchema() {
        return objectMapper.valueToTree(Map.of(
            "type", "object",
            "properties", Map.of(
                "action", Map.of(
                    "type", "string",
                    "enum", List.of("read", "write", "list", "edit"),
                    "description", "要执行的操作"
                ),
                "path", Map.of(
                    "type", "string",
                    "description", "文件或目录路径"
                ),
                "content", Map.of(
                    "type", "string",
                    "description", "写入的内容（write 操作）"
                ),
                "oldString", Map.of(
                    "type", "string",
                    "description", "要替换的文本（edit 操作）"
                ),
                "newString", Map.of(
                    "type", "string",
                    "description", "新文本（edit 操作）"
                )
            ),
            "required", List.of("action", "path")
        ));
    }
    
    @Override
    public ToolResult execute(ToolParameters params) {
        String action = params.getParameters().get("action").toString();
        String pathStr = params.getParameters().get("path").toString();
        
        try {
            Path path = resolvePath(pathStr);
            
            return switch (action) {
                case "read" -> readFile(path);
                case "write" -> writeFile(path, params.getParameters().get("content").toString());
                case "list" -> listDirectory(path);
                case "edit" -> editFile(
                    path,
                    params.getParameters().get("oldString").toString(),
                    params.getParameters().get("newString").toString()
                );
                default -> ToolResult.failure("未知操作: " + action);
            };
        } catch (Exception e) {
            log.error("文件系统操作失败", e);
            return ToolResult.failure(e.getMessage());
        }
    }
    
    private Path resolvePath(String pathStr) {
        Path path = Paths.get(pathStr);
        
        // 如果是相对路径，基于工作空间
        if (!path.isAbsolute()) {
            path = Paths.get(properties.getWorkspacePath()).resolve(path);
        }
        
        // 安全检查：限制在工作空间内
        if (properties.getTools().isRestrictToWorkspace()) {
            Path workspace = Paths.get(properties.getWorkspacePath()).toAbsolutePath().normalize();
            Path resolved = path.toAbsolutePath().normalize();
            
            if (!resolved.startsWith(workspace)) {
                throw new SecurityException("路径超出工作空间范围: " + pathStr);
            }
        }
        
        return path;
    }
    
    private ToolResult readFile(Path path) throws IOException {
        if (!Files.exists(path)) {
            return ToolResult.failure("文件不存在: " + path);
        }
        String content = Files.readString(path);
        return ToolResult.success(content);
    }
    
    private ToolResult writeFile(Path path, String content) throws IOException {
        Files.createDirectories(path.getParent());
        Files.writeString(path, content);
        return ToolResult.success("文件已写入: " + path);
    }
    
    private ToolResult listDirectory(Path path) throws IOException {
        if (!Files.exists(path)) {
            return ToolResult.failure("目录不存在: " + path);
        }
        
        StringBuilder sb = new StringBuilder();
        try (var stream = Files.list(path)) {
            stream.forEach(p -> {
                sb.append(Files.isDirectory(p) ? "[DIR] " : "[FILE] ")
                  .append(p.getFileName())
                  .append("\n");
            });
        }
        return ToolResult.success(sb.toString());
    }
    
    private ToolResult editFile(Path path, String oldString, String newString) throws IOException {
        String content = Files.readString(path);
        if (!content.contains(oldString)) {
            return ToolResult.failure("未找到要替换的文本");
        }
        content = content.replace(oldString, newString);
        Files.writeString(path, content);
        return ToolResult.success("文件已编辑: " + path);
    }
}
```

### 5. Shell 工具实现

```java
package com.nanobot.tools.impl;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanobot.config.NanobotProperties;
import com.nanobot.tools.Tool;
import com.nanobot.tools.ToolParameters;
import com.nanobot.tools.ToolResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.regex.Pattern;

/**
 * Shell 命令执行工具
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ShellTool implements Tool {
    
    private final NanobotProperties properties;
    private final ObjectMapper objectMapper;
    
    // 危险命令模式
    private final List<Pattern> denyPatterns = List.of(
        Pattern.compile("\\brm\\s+-[rf]{1,2}\\b"),          // rm -r, rm -rf
        Pattern.compile("\\bdel\\s+/[fq]\\b"),              // del /f, del /q
        Pattern.compile("\\b(format|mkfs|diskpart)\\b"),   // 磁盘操作
        Pattern.compile("\\b(shutdown|reboot|poweroff)\\b") // 系统电源
    );
    
    @Override
    public String getName() {
        return "shell";
    }
    
    @Override
    public String getDescription() {
        return "执行 shell 命令。有安全限制，禁止危险操作。";
    }
    
    @Override
    public JsonNode getParametersSchema() {
        return objectMapper.valueToTree(Map.of(
            "type", "object",
            "properties", Map.of(
                "command", Map.of(
                    "type", "string",
                    "description", "要执行的命令"
                ),
                "timeout", Map.of(
                    "type", "integer",
                    "description", "超时时间（秒）",
                    "default", 60
                )
            ),
            "required", List.of("command")
        ));
    }
    
    @Override
    public ToolResult execute(ToolParameters params) {
        String command = params.getParameters().get("command").toString();
        int timeout = Integer.parseInt(
            params.getParameters().getOrDefault("timeout", 60).toString()
        );
        
        // 安全检查
        if (!isCommandAllowed(command)) {
            return ToolResult.failure("命令被安全策略阻止: " + command);
        }
        
        try {
            ProcessBuilder pb = new ProcessBuilder("sh", "-c", command);
            
            // 设置工作目录
            Path workspace = Paths.get(properties.getWorkspacePath());
            pb.directory(workspace.toFile());
            
            // 环境变量
            pb.environment().put("PYTHONUNBUFFERED", "1");
            pb.environment().put("FORCE_COLOR", "0");
            pb.environment().put("TERM", "dumb");
            
            Process process = pb.start();
            
            // 读取输出
            StringBuilder stdout = new StringBuilder();
            StringBuilder stderr = new StringBuilder();
            
            try (BufferedReader stdOutReader = new BufferedReader(
                    new InputStreamReader(process.getInputStream()));
                 BufferedReader stdErrReader = new BufferedReader(
                    new InputStreamReader(process.getErrorStream()))) {
                
                String line;
                while ((line = stdOutReader.readLine()) != null) {
                    stdout.append(line).append("\n");
                }
                while ((line = stdErrReader.readLine()) != null) {
                    stderr.append(line).append("\n");
                }
            }
            
            boolean finished = process.waitFor(timeout, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                return ToolResult.failure("命令执行超时");
            }
            
            int exitCode = process.exitValue();
            String output = stdout.toString();
            if (!stderr.isEmpty()) {
                output += "\n[stderr]\n" + stderr;
            }
            
            if (exitCode != 0) {
                return ToolResult.failure("退出码 " + exitCode + ":\n" + output);
            }
            
            return ToolResult.success(output);
            
        } catch (Exception e) {
            log.error("命令执行失败", e);
            return ToolResult.failure(e.getMessage());
        }
    }
    
    private boolean isCommandAllowed(String command) {
        for (Pattern pattern : denyPatterns) {
            if (pattern.matcher(command).find()) {
                return false;
            }
        }
        return true;
    }
}
```

### 6. Agent 服务

```java
package com.nanobot.agent;

import com.alibaba.cloud.ai.toolcalling.ToolCallingManager;
import com.nanobot.tools.ToolRegistry;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

import java.util.ArrayList;
import java.util.List;

/**
 * Agent 服务 - 核心对话处理
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentService {
    
    private final ChatClient chatClient;
    private final ToolRegistry toolRegistry;
    private final ToolCallingManager toolCallingManager;
    private final ContextBuilder contextBuilder;
    
    /**
     * 处理用户消息
     */
    public String processMessage(String userMessage, String sessionId) {
        // 构建上下文
        List<Message> messages = buildContext(sessionId);
        messages.add(new UserMessage(userMessage));
        
        // 创建 Prompt
        Prompt prompt = new Prompt(messages);
        
        // 调用 LLM（带工具）
        ChatResponse response = chatClient.prompt(prompt)
            .tools(toolRegistry.getAllTools())  // 注册所有工具
            .call()
            .chatResponse();
        
        // 处理工具调用循环
        return handleToolCalls(response, messages, sessionId);
    }
    
    /**
     * 流式处理（用于实时响应）
     */
    public Flux<String> processMessageStream(String userMessage, String sessionId) {
        List<Message> messages = buildContext(sessionId);
        messages.add(new UserMessage(userMessage));
        
        return chatClient.prompt(new Prompt(messages))
            .tools(toolRegistry.getAllTools())
            .stream()
            .content();
    }
    
    /**
     * 构建对话上下文
     */
    private List<Message> buildContext(String sessionId) {
        List<Message> messages = new ArrayList<>();
        
        // 系统提示词
        String systemPrompt = contextBuilder.buildSystemPrompt();
        messages.add(new SystemMessage(systemPrompt));
        
        // 历史消息（从 SessionManager 获取）
        // messages.addAll(sessionManager.getHistory(sessionId));
        
        return messages;
    }
    
    /**
     * 处理工具调用循环
     */
    private String handleToolCalls(ChatResponse response, 
                                   List<Message> messages, 
                                   String sessionId) {
        int iterations = 0;
        final int MAX_ITERATIONS = 10;
        
        while (iterations < MAX_ITERATIONS) {
            // 检查是否有工具调用
            if (response.getResult().getOutput().getToolCalls() == null ||
                response.getResult().getOutput().getToolCalls().isEmpty()) {
                // 没有工具调用，返回最终答案
                return response.getResult().getOutput().getContent();
            }
            
            // 执行工具调用
            // Spring AI Alibaba 会自动处理工具调用
            // 这里简化处理，实际可能需要手动循环
            
            iterations++;
        }
        
        return response.getResult().getOutput().getContent();
    }
}
```

### 7. 上下文构建器

```java
package com.nanobot.agent.context;

import com.nanobot.config.NanobotProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * 上下文构建器 - 构建系统提示词
 */
@Component
@RequiredArgsConstructor
public class ContextBuilder {
    
    private final NanobotProperties properties;
    
    /**
     * 构建系统提示词
     */
    public String buildSystemPrompt() {
        StringBuilder prompt = new StringBuilder();
        
        // 基础系统提示
        prompt.append("""
            你是一个名为 nanobot 的 AI 助手。
            
            你可以使用以下工具来帮助用户：
            - filesystem: 读写文件、列出目录
            - shell: 执行 shell 命令
            - web_search: 搜索网页
            - web_fetch: 获取网页内容
            - message: 发送消息
            - spawn: 创建子代理
            - cron: 管理定时任务
            
            指南：
            1. 在采取行动之前解释你正在做什么
            2. 使用工具来完成任务
            3. 保持响应简洁明了
            4. 重要信息记得保存到记忆文件
            """);
        
        // 加载 AGENTS.md
        String agentsMd = loadFile("AGENTS.md");
        if (agentsMd != null) {
            prompt.append("\n\n## 代理指令\n\n").append(agentsMd);
        }
        
        // 加载 SOUL.md
        String soulMd = loadFile("SOUL.md");
        if (soulMd != null) {
            prompt.append("\n\n## 灵魂\n\n").append(soulMd);
        }
        
        // 加载 USER.md
        String userMd = loadFile("USER.md");
        if (userMd != null) {
            prompt.append("\n\n## 用户信息\n\n").append(userMd);
        }
        
        // 加载 MEMORY.md
        String memoryMd = loadFile("memory/MEMORY.md");
        if (memoryMd != null) {
            prompt.append("\n\n## 长期记忆\n\n").append(memoryMd);
        }
        
        return prompt.toString();
    }
    
    private String loadFile(String filename) {
        try {
            Path path = Paths.get(properties.getWorkspacePath(), filename);
            if (Files.exists(path)) {
                return Files.readString(path);
            }
        } catch (IOException e) {
            // 忽略
        }
        return null;
    }
}
```

### 8. 配置文件 (application.yml)

```yaml
spring:
  application:
    name: nanobot
  
  ai:
    # Spring AI Alibaba 配置
    alibaba:
      api-key: ${ALI_API_KEY:}
      base-url: ${ALI_BASE_URL:https://dashscope.aliyuncs.com/api/v1}
      chat:
        options:
          model: qwen-turbo
          temperature: 0.7

nanobot:
  workspace-path: ${user.home}/.nanobot/workspace
  
  agent:
    model: qwen-turbo
    max-tool-iterations: 10
    context-window: 10
  
  channels:
    telegram:
      enabled: false
      token: ${TELEGRAM_TOKEN:}
    discord:
      enabled: false
      token: ${DISCORD_TOKEN:}
  
  tools:
    restrict-to-workspace: true
    shell:
      timeout: 60
    web:
      search-api-key: ${BRAVE_API_KEY:}

# 日志
logging:
  level:
    com.nanobot: INFO
    org.springframework.ai: DEBUG
```

## Spring AI Alibaba 特性使用

### 1. 工具调用 (Function Calling)

```java
// Spring AI Alibaba 自动处理工具调用
@Bean
public ChatClient chatClient(ChatClient.Builder builder, 
                             ToolRegistry toolRegistry) {
    return builder
        .defaultTools(toolRegistry.getAllTools())
        .build();
}
```

### 2. 流式响应

```java
// 支持 SSE 流式输出
@GetMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public Flux<String> chatStream(@RequestParam String message) {
    return agentService.processMessageStream(message, "default");
}
```

### 3. 多模态支持

```java
// 支持图片、文档等
UserMessage message = new UserMessage(
    "分析这张图片",
    new Media(MimeTypeUtils.IMAGE_PNG, imageResource)
);
```

## 与 Python 版本的对比

| 特性 | Python (nanobot) | Java (Nanobot4J) |
|------|-----------------|------------------|
| **异步模型** | asyncio | Virtual Threads (Java 21+) |
| **类型安全** | 运行时检查 | 编译时检查 |
| **性能** | GIL 限制 | 真正的多线程 |
| **工具调用** | 手动实现 | Spring AI 自动处理 |
| **配置管理** | Pydantic | Spring Boot Configuration |
| **定时任务** | 自定义 | Quartz Scheduler |
| **依赖注入** | 手动 | Spring IoC |
| **监控运维** | 有限 | Spring Boot Actuator |

## 实现建议

1. **优先实现核心功能**：Agent 循环、工具系统、文件操作
2. **使用 Spring AI Alibaba 的工具调用**：避免手动实现工具调用循环
3. **利用 Virtual Threads**：简化异步编程模型
4. **模块化设计**：每个频道、工具独立实现
5. **完善的测试**：利用 Spring Boot Test 进行单元测试和集成测试

## 后续扩展

- [ ] Telegram 频道集成
- [ ] Discord 频道集成
- [ ] Web 搜索工具
- [ ] 定时任务系统
- [ ] 记忆系统持久化
- [ ] 语音转录支持
- [ ] 多代理协作
- [ ] Web UI 界面

---

**文档版本**: 1.0.0  
**基于**: Spring AI Alibaba 1.1.2.0  
**创建日期**: 2026-02-07
