export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  
  // 从环境变量获取 Vercel 后端地址
  // 格式应该是: https://your-project.vercel.app
  const backendUrl = env.VERCEL_BACKEND_URL;
  
  if (!backendUrl) {
    return new Response(
      JSON.stringify({ 
        success: false, 
        error: "后端地址未配置 (VERCEL_BACKEND_URL missing)" 
      }), 
      {
        status: 500,
        headers: { "Content-Type": "application/json" }
      }
    );
  }

  // 构建目标 URL
  // 将当前请求的路径 (e.g., /api/generate) 拼接到 Vercel 域名后
  const targetUrl = new URL(url.pathname + url.search, backendUrl);

  // 创建新请求，保留原始方法、头信息和请求体
  const proxyRequest = new Request(targetUrl, {
    method: request.method,
    headers: request.headers,
    body: request.body,
    redirect: "follow"
  });

  try {
    const response = await fetch(proxyRequest);
    return response;
  } catch (e) {
    return new Response(
      JSON.stringify({ 
        success: false, 
        error: `代理请求失败: ${e.message}` 
      }), 
      { 
        status: 500,
        headers: { "Content-Type": "application/json" }
      }
    );
  }
}

