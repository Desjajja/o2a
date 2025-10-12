import { useEffect, useState } from "react";
import {
  ProviderConfig,
  fetchConfig,
  saveConfig,
  applyRestart
} from "../services/api";

interface EditableProvider extends ProviderConfig {
  isExpanded?: boolean;
}

const randomId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `prov-${Math.random().toString(36).slice(2, 10)}`;

const emptyProvider = (): EditableProvider => ({
  id: randomId(),
  name: "New Provider",
  base_url: "https://api.openai.com/v1",
  api_key: "",
  models: [
    { proxy_name: "claude-sonnet-4-5-20250929", upstream_name: "gpt-4.1" }
  ],
  isExpanded: true
});

const ConfigPage = () => {
  const [providers, setProviders] = useState<EditableProvider[]>([]);
  const [needsRestart, setNeedsRestart] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchConfig();
        setProviders(data.providers.map((provider) => ({ ...provider, isExpanded: false })));
        setNeedsRestart(data.needs_restart);
      } catch (err) {
        setError("Failed to load configuration");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const toggleProvider = (id: string) => {
    setProviders((current) =>
      current.map((provider) =>
        provider.id === id ? { ...provider, isExpanded: !provider.isExpanded } : provider
      )
    );
  };

  const updateProvider = (id: string, field: keyof ProviderConfig, value: string) => {
    setProviders((current) =>
      current.map((provider) =>
        provider.id === id ? { ...provider, [field]: value } : provider
      )
    );
  };

  const updateModel = (
    providerId: string,
    index: number,
    field: "proxy_name" | "upstream_name",
    value: string
  ) => {
    setProviders((current) =>
      current.map((provider) => {
        if (provider.id !== providerId) {
          return provider;
        }
        const models = provider.models.map((model, modelIndex) =>
          modelIndex === index ? { ...model, [field]: value } : model
        );
        return { ...provider, models };
      })
    );
  };

  const addModel = (providerId: string) => {
    setProviders((current) =>
      current.map((provider) =>
        provider.id === providerId
          ? {
              ...provider,
              models: [
                ...provider.models,
                { proxy_name: "claude-3-5-haiku-20241022", upstream_name: "gpt-4.1-mini" }
              ]
            }
          : provider
      )
    );
  };

  const removeModel = (providerId: string, index: number) => {
    setProviders((current) =>
      current.map((provider) =>
        provider.id === providerId
          ? {
              ...provider,
              models: provider.models.filter((_, modelIndex) => modelIndex !== index)
            }
          : provider
      )
    );
  };

  const addProvider = () => {
    setProviders((current) => [...current, emptyProvider()]);
  };

  const removeProvider = (id: string) => {
    setProviders((current) => current.filter((provider) => provider.id !== id));
  };

  const handleSave = async () => {
    try {
      setError(null);
      const response = await saveConfig(
        providers.map(({ isExpanded, ...provider }) => provider)
      );
      setProviders(response.providers.map((provider) => ({ ...provider, isExpanded: false })));
      setNeedsRestart(response.needs_restart);
    } catch (err) {
      setError("Failed to save configuration");
    }
  };

  const handleRestart = async () => {
    try {
      const response = await applyRestart();
      setProviders(response.providers.map((provider) => ({ ...provider, isExpanded: false })));
      setNeedsRestart(response.needs_restart);
    } catch (err) {
      setError("Failed to restart proxy");
    }
  };

  const hasProviders = providers.length > 0;

  const headerActions = needsRestart ? (
    <div className="restart-banner">
      <span className="helper-text">Restart required to apply saved changes.</span>
      <button className="primary-button" onClick={handleRestart}>
        Restart to Apply
      </button>
    </div>
  ) : null;

  if (loading) {
    return (
      <div className="page-container">
        <p>Loading configuration...</p>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2>Providers</h2>
          <p className="helper-text">Base URL + API key identifies each upstream provider.</p>
        </div>
        <div>{headerActions}</div>
      </div>

      {error && <p className="error-text">{error}</p>}

      {hasProviders ? (
        providers.map((provider) => (
          <section className="card" key={provider.id}>
            <div className="provider-header">
              <div>
                <h3>{provider.name}</h3>
                <p className="helper-text">{provider.base_url}</p>
              </div>
              <div>
                <button className="secondary-button" onClick={() => toggleProvider(provider.id)}>
                  {provider.isExpanded ? "Collapse" : "Expand"}
                </button>
                <button className="muted-button" onClick={() => removeProvider(provider.id)}>
                  Remove
                </button>
              </div>
            </div>
            {provider.isExpanded && (
              <div className="provider-body">
                <fieldset>
                  <label htmlFor={`name-${provider.id}`}>Provider Name</label>
                  <input
                    id={`name-${provider.id}`}
                    value={provider.name}
                    onChange={(event) => updateProvider(provider.id, "name", event.target.value)}
                  />
                </fieldset>
                <fieldset>
                  <label htmlFor={`base-${provider.id}`}>Base URL</label>
                  <input
                    id={`base-${provider.id}`}
                    value={provider.base_url}
                    onChange={(event) => updateProvider(provider.id, "base_url", event.target.value)}
                  />
                </fieldset>
                <fieldset>
                  <label htmlFor={`key-${provider.id}`}>API Key</label>
                  <input
                    id={`key-${provider.id}`}
                    value={provider.api_key}
                    placeholder="sk-..."
                    onChange={(event) => updateProvider(provider.id, "api_key", event.target.value)}
                  />
                </fieldset>

                <div>
                  <div className="provider-header" style={{ marginBottom: "12px" }}>
                    <strong>Model Mappings</strong>
                    <button className="secondary-button" onClick={() => addModel(provider.id)}>
                      Add model
                    </button>
                  </div>
                  {provider.models.map((model, index) => (
                    <div className="model-grid" key={`${provider.id}-${index}`}>
                      <div>
                        <label htmlFor={`proxy-${provider.id}-${index}`}>Proxy Name</label>
                        <input
                          id={`proxy-${provider.id}-${index}`}
                          value={model.proxy_name}
                          onChange={(event) =>
                            updateModel(provider.id, index, "proxy_name", event.target.value)
                          }
                        />
                      </div>
                      <div>
                        <label htmlFor={`upstream-${provider.id}-${index}`}>Upstream Model</label>
                        <input
                          id={`upstream-${provider.id}-${index}`}
                          value={model.upstream_name}
                          onChange={(event) =>
                            updateModel(provider.id, index, "upstream_name", event.target.value)
                          }
                        />
                      </div>
                      <div>
                        <button className="muted-button" onClick={() => removeModel(provider.id, index)}>
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        ))
      ) : (
        <section className="card">
          <p className="helper-text">No providers configured yet.</p>
        </section>
      )}

      <div style={{ display: "flex", gap: "12px" }}>
        <button className="secondary-button" onClick={addProvider}>
          Add Provider
        </button>
        <button className="primary-button" onClick={handleSave} disabled={providers.length === 0}>
          Save Changes
        </button>
      </div>
    </div>
  );
};

export default ConfigPage;
