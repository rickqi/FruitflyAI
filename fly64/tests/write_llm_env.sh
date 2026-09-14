#!/bin/bash
# LLM consultant env — ROOT-ONLY, never commit this file (contains API key).
cat > /root/fly64/plugin/llm.env <<'EOF'
export FLY64_LLM_TRANSPORT=http
export FLY64_LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
export FLY64_LLM_API_KEY=***REDACTED***
export FLY64_LLM_MODEL=glm-5.3-flash
EOF
chmod 600 /root/fly64/plugin/llm.env
grep -q "llm.env" /mnt/d/codes/flygym/.gitignore 2>/dev/null || echo "fly64/plugin/llm.env" >> /mnt/d/codes/flygym/.gitignore
echo "llm.env written (root-only)"
