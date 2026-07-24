import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import type { Campaign, GrowthAsset, Recommendation } from "../types";
import {
  Badge,
  Empty,
  Notice,
  PageHeader,
  Panel,
  type NoticeState,
} from "../components/UI";

export function GrowthPage() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [assets, setAssets] = useState<GrowthAsset[]>([]);
  const [notice, setNotice] = useState<NoticeState>(null);
  const [form, setForm] = useState({
    recommendation_id: "",
    name: "",
    channel: "email",
    audience: "",
    goal: "",
  });
  const [assetForm, setAssetForm] = useState({
    campaign_id: "",
    asset_type: "email",
    tone: "clear, credible and founder-led",
  });

  const load = useCallback(async () => {
    const [recommendationData, campaignData, assetData] = await Promise.all([
      api.get<Recommendation[]>("/recommendations"),
      api.get<Campaign[]>("/growth/campaigns"),
      api.get<GrowthAsset[]>("/growth/assets"),
    ]);
    setRecommendations(recommendationData);
    setCampaigns(campaignData);
    setAssets(assetData);
  }, []);

  useEffect(() => {
    load().catch((error) =>
      setNotice({ kind: "error", text: (error as Error).message }),
    );
  }, [load]);

  const approved = useMemo(
    () => recommendations.filter((item) => item.status === "approved"),
    [recommendations],
  );

  async function createCampaign(event: FormEvent) {
    event.preventDefault();
    try {
      const campaign = await api.post<Campaign>("/growth/campaigns", form);
      setAssetForm({ ...assetForm, campaign_id: campaign.id });
      setNotice({
        kind: "success",
        text: "Campaign created from the approved priority.",
      });
      setForm({ ...form, name: "", audience: "", goal: "" });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    }
  }

  async function generateAsset(event: FormEvent) {
    event.preventDefault();
    try {
      await api.post(`/growth/campaigns/${assetForm.campaign_id}/assets`, {
        asset_type: assetForm.asset_type,
        tone: assetForm.tone,
      });
      setNotice({
        kind: "success",
        text: "Campaign content generated and sent for approval.",
      });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    }
  }

  return (
    <section className="page">
      <PageHeader
        eyebrow="Execution"
        title="Campaigns & Content"
        description="Turn approved priorities into campaigns, messages and launch materials that remain under your control."
      />
      <Notice notice={notice} />

      <div className="two-column align-start">
        <Panel>
          <h3>Create campaign from an approved priority</h3>
          <form className="form-grid" onSubmit={createCampaign}>
            <label className="full">
              Approved priority
              <select
                required
                value={form.recommendation_id}
                onChange={(event) =>
                  setForm({ ...form, recommendation_id: event.target.value })
                }
              >
                <option value="">Select priority</option>
                {approved.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Campaign name
              <input
                required
                value={form.name}
                onChange={(event) =>
                  setForm({ ...form, name: event.target.value })
                }
              />
            </label>
            <label>
              Channel
              <select
                value={form.channel}
                onChange={(event) =>
                  setForm({ ...form, channel: event.target.value })
                }
              >
                {[
                  "email",
                  "social",
                  "launch",
                  "landing_page",
                  "blog",
                  "newsletter",
                  "release_notes",
                ].map((channel) => (
                  <option value={channel} key={channel}>
                    {channel.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <label className="full">
              Audience
              <input
                required
                value={form.audience}
                onChange={(event) =>
                  setForm({ ...form, audience: event.target.value })
                }
              />
            </label>
            <label className="full">
              Goal
              <input
                required
                value={form.goal}
                onChange={(event) =>
                  setForm({ ...form, goal: event.target.value })
                }
              />
            </label>
            <button type="submit">Create campaign</button>
          </form>
        </Panel>

        <Panel>
          <h3>Generate campaign content</h3>
          <form className="form-grid" onSubmit={generateAsset}>
            <label className="full">
              Campaign
              <select
                required
                value={assetForm.campaign_id}
                onChange={(event) =>
                  setAssetForm({ ...assetForm, campaign_id: event.target.value })
                }
              >
                <option value="">Select campaign</option>
                {campaigns.map((campaign) => (
                  <option value={campaign.id} key={campaign.id}>
                    {campaign.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Content type
              <select
                value={assetForm.asset_type}
                onChange={(event) =>
                  setAssetForm({ ...assetForm, asset_type: event.target.value })
                }
              >
                {[
                  "email",
                  "social_post",
                  "launch_post",
                  "landing_page",
                  "blog_outline",
                  "newsletter",
                  "release_notes",
                ].map((type) => (
                  <option value={type} key={type}>
                    {type.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Tone
              <input
                value={assetForm.tone}
                onChange={(event) =>
                  setAssetForm({ ...assetForm, tone: event.target.value })
                }
              />
            </label>
            <button type="submit">Generate for approval</button>
          </form>
        </Panel>
      </div>

      <div className="two-column align-start">
        <Panel>
          <div className="section-heading">
            <div>
              <span>Execution plans</span>
              <h3>Campaigns</h3>
            </div>
          </div>
          <div className="stack">
            {campaigns.length ? (
              campaigns.map((campaign) => (
                <article className="campaign-card" key={campaign.id}>
                  <div className="card-topline">
                    <Badge>{campaign.channel}</Badge>
                    <Badge
                      tone={campaign.status === "active" ? "good" : "neutral"}
                    >
                      {campaign.status}
                    </Badge>
                  </div>
                  <h4>{campaign.name}</h4>
                  <p>{campaign.goal}</p>
                  <small>{campaign.assets_created} item(s) prepared</small>
                </article>
              ))
            ) : (
              <Empty>No campaign has been created.</Empty>
            )}
          </div>
        </Panel>

        <Panel>
          <div className="section-heading">
            <div>
              <span>Prepared content</span>
              <h3>Generated materials</h3>
            </div>
          </div>
          <div className="stack">
            {assets.length ? (
              assets.map((asset) => (
                <article className="asset-card" key={asset.id}>
                  <div className="card-topline">
                    <Badge>{asset.asset_type.replaceAll("_", " ")}</Badge>
                    <Badge
                      tone={
                        asset.status === "executed_mock" ? "good" : "neutral"
                      }
                    >
                      {asset.status}
                    </Badge>
                  </div>
                  <h4>{asset.title}</h4>
                  <pre>{asset.content}</pre>
                  {asset.grounding_facts.length > 0 && (
                    <details>
                      <summary>Verified source facts</summary>
                      <ul>
                        {asset.grounding_facts.map((fact) => (
                          <li key={fact}>{fact}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </article>
              ))
            ) : (
              <Empty>No campaign content has been generated.</Empty>
            )}
          </div>
        </Panel>
      </div>
    </section>
  );
}
