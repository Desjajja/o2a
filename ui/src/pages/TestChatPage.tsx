import { FormEvent, useEffect, useMemo, useState } from "react";
import { AnthropicMessage, ProviderConfig, fetchConfig, sendTestChat } from "../services/api";

interface ChatEntry {
  role: "user" | "assistant";
  text: string;
}

const defaultMessage = "Test the proxy connection.";

const TestChatPage = () => {
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [input, setInput] = useState(defaultMessage);
  const [chatLog, setChatLog] = useState<ChatEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchConfig();
        setProviders(data.providers);
        const firstProvider = data.providers[0];
        if (firstProvider) {
          setSelectedProvider(firstProvider.id);
          setSelectedModel(firstProvider.models[0]?.proxy_name ?? null);
        }
      } catch (err) {
        setError("Failed to load providers");
      }
    };

    load();
  }, []);

  const availableModels = useMemo(() => {
    if (!selectedProvider) {
      return [];
    }
    const provider = providers.find((item) => item.id === selectedProvider);
    return provider?.models ?? [];
  }, [providers, selectedProvider]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedModel) {
      setError("Select a model to send a test chat");
      return;
    }

    setError(null);
    setLoading(true);
    const userMessage: AnthropicMessage = {
      role: "user",
      content: [{ type: "text", text: input }]
    };

    setChatLog((current) => [...current, { role: "user", text: input }]);

    try {
      const response = await sendTestChat({
        model: selectedModel,
        messages: [userMessage],
        max_tokens: 256
      });

      const assistantText = response?.content?.[0]?.text ?? "(no response)";
      setChatLog((current) => [...current, { role: "assistant", text: assistantText }]);
      setInput("");
    } catch (err) {
      setError("Proxy test failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2>Test Chat</h2>
          <p className="helper-text">Send Anthropic-formatted prompt through the proxy.</p>
        </div>
      </div>

      {error && <p className="error-text">{error}</p>}

      <div className="chat-layout">
        <aside className="sidebar">
          <div>
            <label htmlFor="providerSelect">Provider</label>
           <select
              id="providerSelect"
              value={selectedProvider ?? ""}
              onChange={(event) => {
                const next = event.target.value || null;
                setSelectedProvider(next);
                const nextProvider = providers.find((item) => item.id === next);
                setSelectedModel(nextProvider?.models[0]?.proxy_name ?? null);
              }}
            >
              <option value="" disabled>
                Select provider
              </option>
              {providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="modelSelect">Model</label>
            <select
              id="modelSelect"
              value={selectedModel ?? ""}
              onChange={(event) => setSelectedModel(event.target.value || null)}
            >
              <option value="" disabled>
                Select model
              </option>
              {availableModels.map((model) => (
                <option key={model.proxy_name} value={model.proxy_name}>
                  {model.proxy_name}
                </option>
              ))}
            </select>
          </div>
        </aside>

        <section className="chat-pane">
          <div className="chat-log">
            {chatLog.length === 0 ? (
              <p className="helper-text">Send a prompt to verify proxy translation.</p>
            ) : (
              chatLog.map((entry, index) => (
                <div className="chat-entry" key={index}>
                  <strong>{entry.role === "user" ? "You" : "Assistant"}</strong>
                  <span>{entry.text}</span>
                </div>
              ))
            )}
          </div>
          <form className="chat-input" onSubmit={onSubmit}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask something to the proxy"
            />
            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? "Sending..." : "Send"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
};

export default TestChatPage;
