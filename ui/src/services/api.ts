import axios from "axios";

export interface ModelMapping {
  proxy_name: string;
  upstream_name: string;
}

export interface ProviderConfig {
  id: string;
  name: string;
  base_url: string;
  api_key: string;
  models: ModelMapping[];
}

export interface ConfigResponse {
  providers: ProviderConfig[];
  needs_restart: boolean;
  staged_at?: number | null;
}

export interface AnthropicMessageBlock {
  type: "text";
  text: string;
}

export interface AnthropicMessage {
  role: "user" | "assistant" | "system";
  content: AnthropicMessageBlock[];
}

export interface ChatPayload {
  model: string;
  messages: AnthropicMessage[];
  max_tokens?: number;
  stream?: boolean;
}

const client = axios.create({ baseURL: "/" });

export const fetchConfig = async (): Promise<ConfigResponse> => {
  const { data } = await client.get<ConfigResponse>("/admin/config");
  return data;
};

export const saveConfig = async (providers: ProviderConfig[]): Promise<ConfigResponse> => {
  const { data } = await client.put<ConfigResponse>("/admin/config", { providers });
  return data;
};

export const applyRestart = async (): Promise<ConfigResponse> => {
  const { data } = await client.post<ConfigResponse>("/admin/restart");
  return data;
};

export const sendTestChat = async (payload: ChatPayload) => {
  const { data } = await client.post("/admin/test-chat", payload);
  return data;
};

export const fetchModels = async () => {
  const { data } = await client.get("/v1/models");
  return data;
};
