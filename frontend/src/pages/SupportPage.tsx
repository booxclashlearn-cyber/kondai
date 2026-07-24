import {
  FormEvent,
  useCallback,
  useEffect,
  useState,
} from "react";
import { api } from "../lib/api";
import type {
  SupportTicket,
  WhatsAppConversation,
  WhatsAppMessage,
} from "../types";
import {
  Badge,
  Empty,
  Notice,
  PageHeader,
  Panel,
  type NoticeState,
} from "../components/UI";

export function SupportPage() {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [conversations, setConversations] = useState<WhatsAppConversation[]>([]);
  const [selected, setSelected] = useState<WhatsAppConversation | null>(null);
  const [messages, setMessages] = useState<WhatsAppMessage[]>([]);
  const [notice, setNotice] = useState<NoticeState>(null);
  const [form, setForm] = useState({
    customer_name: "",
    customer_email: "",
    subject: "",
    message: "",
    priority: "medium",
  });

  const load = useCallback(async () => {
    const [ticketData, conversationData] = await Promise.all([
      api.get<SupportTicket[]>("/support/tickets"),
      api
        .get<WhatsAppConversation[]>(
          "/integrations/whatsapp/conversations",
        )
        .catch(() => []),
    ]);
    setTickets(ticketData);
    setConversations(conversationData);
  }, []);

  useEffect(() => {
    load().catch((error) =>
      setNotice({ kind: "error", text: (error as Error).message }),
    );
  }, [load]);

  async function openConversation(conversation: WhatsAppConversation) {
    setSelected(conversation);
    try {
      const result = await api.get<WhatsAppMessage[]>(
        `/integrations/whatsapp/conversations/${conversation.id}/messages`,
      );
      setMessages(result);
      if (conversation.unread_count > 0) {
        await api.post(
          `/integrations/whatsapp/conversations/${conversation.id}/mark-read`,
        );
        await load();
      }
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    }
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      await api.post("/support/tickets", form);
      setForm({
        customer_name: "",
        customer_email: "",
        subject: "",
        message: "",
        priority: "medium",
      });
      setNotice({ kind: "success", text: "Customer issue created." });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    }
  }

  async function draft(ticket: SupportTicket) {
    try {
      const response = await api.post<{ escalated: boolean }>(
        `/support/tickets/${ticket.id}/draft`,
      );
      setNotice({
        kind: "success",
        text: response.escalated
          ? "The issue was escalated because there was not enough verified information."
          : ticket.channel === "whatsapp"
            ? "A WhatsApp reply was prepared and sent for approval."
            : "A verified response was prepared and sent for approval.",
      });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    }
  }

  const selectedTicket = selected
    ? tickets.find((ticket) => ticket.id === selected.ticket_id)
    : undefined;

  return (
    <section className="page">
      <PageHeader
        eyebrow="Customers"
        title="Customer Care"
        description="See customer conversations, prepare verified responses and capture recurring feedback."
      />
      <Notice notice={notice} />

      <Panel className="whatsapp-inbox-panel">
        <div className="section-heading">
          <div>
            <span>WhatsApp</span>
            <h3>Live customer conversations</h3>
          </div>
          <small>
            New messages appear here after the Meta webhook is verified.
          </small>
        </div>

        {conversations.length ? (
          <div className="chat-inbox">
            <aside className="chat-conversation-list">
              {conversations.map((conversation) => (
                <button
                  type="button"
                  className={
                    selected?.id === conversation.id
                      ? "chat-conversation active"
                      : "chat-conversation"
                  }
                  key={conversation.id}
                  onClick={() => openConversation(conversation)}
                >
                  <div>
                    <strong>
                      {conversation.customer_name ||
                        conversation.customer_phone}
                    </strong>
                    <span>{conversation.last_message}</span>
                  </div>
                  <div>
                    {conversation.unread_count > 0 && (
                      <b>{conversation.unread_count}</b>
                    )}
                    <small>
                      {conversation.last_message_at
                        ? new Date(
                            conversation.last_message_at,
                          ).toLocaleString()
                        : ""}
                    </small>
                  </div>
                </button>
              ))}
            </aside>

            <div className="chat-thread">
              {selected ? (
                <>
                  <div className="chat-thread-header">
                    <div>
                      <strong>{selected.customer_name}</strong>
                      <span>+{selected.customer_phone}</span>
                    </div>
                    {selectedTicket && selectedTicket.status === "open" && (
                      <button onClick={() => draft(selectedTicket)}>
                        Prepare verified reply
                      </button>
                    )}
                  </div>
                  <div className="chat-messages">
                    {messages.map((message) => (
                      <article
                        className={
                          message.direction === "inbound"
                            ? "chat-bubble inbound"
                            : "chat-bubble outbound"
                        }
                        key={message.id}
                      >
                        <p>{message.body}</p>
                        <small>
                          {new Date(
                            message.provider_timestamp,
                          ).toLocaleString()} · {message.delivery_status}
                        </small>
                      </article>
                    ))}
                  </div>
                  <p className="chat-approval-note">
                    Replies are created from the linked customer issue and must
                    be approved before Kondai sends them through WhatsApp.
                  </p>
                </>
              ) : (
                <Empty>Select a WhatsApp conversation to read the chat.</Empty>
              )}
            </div>
          </div>
        ) : (
          <Empty>
            No WhatsApp chats have arrived. Connect WhatsApp, verify the webhook
            in Meta and send a message to the business number.
          </Empty>
        )}
      </Panel>

      <div className="two-column align-start">
        <Panel>
          <h3>Add customer issue manually</h3>
          <form className="form-grid" onSubmit={create}>
            <label>
              Customer
              <input
                required
                value={form.customer_name}
                onChange={(event) =>
                  setForm({ ...form, customer_name: event.target.value })
                }
              />
            </label>
            <label>
              Email
              <input
                type="email"
                required
                value={form.customer_email}
                onChange={(event) =>
                  setForm({ ...form, customer_email: event.target.value })
                }
              />
            </label>
            <label className="full">
              Subject
              <input
                required
                value={form.subject}
                onChange={(event) =>
                  setForm({ ...form, subject: event.target.value })
                }
              />
            </label>
            <label className="full">
              Message
              <textarea
                required
                value={form.message}
                onChange={(event) =>
                  setForm({ ...form, message: event.target.value })
                }
              />
            </label>
            <label>
              Priority
              <select
                value={form.priority}
                onChange={(event) =>
                  setForm({ ...form, priority: event.target.value })
                }
              >
                {[
                  "low",
                  "medium",
                  "high",
                  "urgent",
                ].map((priority) => (
                  <option value={priority} key={priority}>
                    {priority}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit">Add issue</button>
          </form>
        </Panel>

        <Panel>
          <div className="section-heading">
            <div>
              <span>Customer voice</span>
              <h3>Issue queue</h3>
            </div>
          </div>
          <div className="stack">
            {tickets.length ? (
              tickets.map((ticket) => (
                <article className="ticket-card" key={ticket.id}>
                  <div className="card-topline">
                    <Badge tone={ticket.priority}>{ticket.priority}</Badge>
                    <Badge
                      tone={
                        ticket.status === "resolved"
                          ? "good"
                          : ticket.status === "escalated"
                            ? "critical"
                            : "neutral"
                      }
                    >
                      {ticket.status}
                    </Badge>
                    {ticket.channel === "whatsapp" && (
                      <Badge tone="good">WhatsApp</Badge>
                    )}
                  </div>
                  <h4>{ticket.subject}</h4>
                  <p>{ticket.latest_message || ticket.message}</p>
                  <small>
                    {ticket.customer_name} ·{" "}
                    {ticket.channel === "whatsapp"
                      ? ticket.customer_phone
                      : ticket.customer_email}
                  </small>
                  {ticket.escalation_reason && (
                    <div className="reason-box">
                      <strong>Escalation</strong>
                      <p>{ticket.escalation_reason}</p>
                    </div>
                  )}
                  {ticket.status === "open" && (
                    <button
                      className="secondary"
                      onClick={() => draft(ticket)}
                    >
                      Prepare verified response
                    </button>
                  )}
                </article>
              ))
            ) : (
              <Empty>No customer issues are waiting.</Empty>
            )}
          </div>
        </Panel>
      </div>
    </section>
  );
}
