import { useEffect } from "react";

const CONTACT_EMAIL = "booxclash@gmail.com";
const EFFECTIVE_DATE = "25 July 2026";

const sections = [
  ["who-we-are", "1. Who we are"],
  ["scope", "2. Scope"],
  ["data", "3. Information we collect"],
  ["use", "4. How we use information"],
  ["integrations", "5. Connected services"],
  ["ai", "6. Artificial intelligence"],
  ["sharing", "7. Sharing"],
  ["retention", "8. Retention"],
  ["security", "9. Security"],
  ["transfers", "10. International transfers"],
  ["rights", "11. Your rights"],
  ["deletion", "12. Data deletion"],
  ["children", "13. Children"],
  ["changes", "14. Changes"],
  ["contact", "15. Contact"],
] as const;

function PrivacySection({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="privacy-section">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export default function PrivacyPage() {
  useEffect(() => {
    document.title = "Privacy Policy | Kondai";
  }, []);

  return (
    <main className="privacy-page">
      <style>{`
        :root {
          --ink:#251421;
          --plum:#4A2840;
          --cream:#FAEDCD;
          --paper:#FFF9EF;
          --muted:#6f5a68;
          --line:rgba(74,40,64,.16);
        }
        *{box-sizing:border-box}
        html{scroll-behavior:smooth}
        body{margin:0}
        .privacy-page{
          min-height:100vh;
          color:var(--ink);
          background:
            radial-gradient(circle at top right,rgba(250,237,205,.95),transparent 34rem),
            var(--paper);
          font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
          line-height:1.7;
        }
        .privacy-hero{background:var(--ink);color:var(--paper)}
        .privacy-hero-inner{width:min(1180px,calc(100% - 40px));margin:auto;padding:28px 0 72px}
        .privacy-brand{display:inline-flex;align-items:center;gap:12px;color:inherit;text-decoration:none}
        .privacy-mark{display:grid;width:42px;height:42px;place-items:center;border-radius:13px;background:var(--cream);color:var(--ink);font-weight:900}
        .privacy-brand strong,.privacy-brand small{display:block}
        .privacy-brand small{margin-top:3px;color:rgba(255,249,239,.7);font-size:.72rem}
        .privacy-heading{max-width:760px;padding-top:74px}
        .privacy-eyebrow{margin:0 0 12px;color:var(--cream);font-size:.76rem;font-weight:800;letter-spacing:.18em}
        .privacy-heading h1{margin:0;font-size:clamp(2.8rem,8vw,5.7rem);line-height:.96;letter-spacing:-.055em}
        .privacy-intro{max-width:680px;margin:28px 0 0;color:rgba(255,249,239,.78);font-size:clamp(1rem,2vw,1.22rem)}
        .privacy-date{margin:22px 0 0;color:rgba(255,249,239,.68);font-size:.92rem}
        .privacy-layout{display:grid;grid-template-columns:245px minmax(0,780px);gap:48px;width:min(1100px,calc(100% - 40px));margin:-32px auto 0;align-items:start}
        .privacy-toc{position:sticky;top:22px;padding:24px;border:1px solid var(--line);border-radius:22px;background:rgba(255,249,239,.9);box-shadow:0 18px 50px rgba(37,20,33,.06)}
        .privacy-toc p{margin:0 0 13px;color:var(--plum);font-size:.74rem;font-weight:850;letter-spacing:.12em;text-transform:uppercase}
        .privacy-toc a{display:block;padding:5px 0;color:var(--muted);font-size:.82rem;line-height:1.35;text-decoration:none}
        .privacy-card{overflow:hidden;border:1px solid var(--line);border-radius:28px;background:rgba(255,255,255,.88);box-shadow:0 24px 80px rgba(37,20,33,.08)}
        .privacy-summary{margin:28px;padding:20px 22px;border-left:4px solid var(--plum);border-radius:0 15px 15px 0;background:var(--cream)}
        .privacy-section{padding:38px 46px;border-top:1px solid var(--line);scroll-margin-top:24px}
        .privacy-section h2{margin:0 0 18px;font-size:clamp(1.45rem,3vw,2rem);line-height:1.2;letter-spacing:-.025em}
        .privacy-section h3{margin:25px 0 8px;color:var(--plum);font-size:1.05rem}
        .privacy-section p{margin:0 0 15px;color:var(--muted)}
        .privacy-section ul{margin:8px 0 18px;padding-left:22px;color:var(--muted)}
        .privacy-section li{margin:7px 0}
        .privacy-section a{color:var(--plum);font-weight:700;text-underline-offset:3px}
        .privacy-contact{display:grid;gap:4px;padding:22px;border:1px solid var(--line);border-radius:18px;background:var(--paper);color:var(--muted);font-style:normal}
        .privacy-footer{display:flex;justify-content:space-between;gap:20px;width:min(1100px,calc(100% - 40px));margin:auto;padding:42px 0;color:var(--muted);font-size:.88rem}
        .privacy-footer a{color:var(--plum);font-weight:750;text-decoration:none}
        @media(max-width:900px){.privacy-layout{grid-template-columns:1fr;gap:20px;margin-top:-26px}.privacy-toc{display:none}}
        @media(max-width:640px){.privacy-hero-inner,.privacy-layout,.privacy-footer{width:min(100% - 24px,1100px)}.privacy-heading{padding-top:52px}.privacy-card{border-radius:22px}.privacy-summary{margin:18px}.privacy-section{padding:30px 24px}.privacy-footer{flex-direction:column;padding:30px 0}}
      `}</style>

      <header className="privacy-hero">
        <div className="privacy-hero-inner">
          <a className="privacy-brand" href="/">
            <span className="privacy-mark">K</span>
            <span>
              <strong>Kondai</strong>
              <small>by Booxclash Learn LTD</small>
            </span>
          </a>

          <div className="privacy-heading">
            <p className="privacy-eyebrow">LEGAL</p>
            <h1>Privacy Policy</h1>
            <p className="privacy-intro">
              This policy explains how Booxclash Learn LTD collects, uses,
              stores and protects information when people use Kondai and connect
              business services.
            </p>
            <p className="privacy-date">
              Effective date: <strong>{EFFECTIVE_DATE}</strong>
            </p>
          </div>
        </div>
      </header>

      <div className="privacy-layout">
        <aside className="privacy-toc" aria-label="Privacy policy contents">
          <p>Contents</p>
          {sections.map(([id, label]) => (
            <a key={id} href={`#${id}`}>
              {label}
            </a>
          ))}
        </aside>

        <article className="privacy-card">
          <div className="privacy-summary">
            <strong>Summary:</strong> Kondai uses information you provide and
            business systems you choose to connect so it can organise
            operations, prepare insights and support customer conversations. We
            do not sell personal information.
          </div>

          <PrivacySection id="who-we-are" title="1. Who we are">
            <p>
              Kondai is a founder operations platform operated by{" "}
              <strong>Booxclash Learn LTD</strong>, a company based in Zambia.
              “Booxclash Learn,” “Kondai,” “we,” “us” and “our” refer to
              Booxclash Learn LTD.
            </p>
            <p>
              Contact:{" "}
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
            </p>
          </PrivacySection>

          <PrivacySection id="scope" title="2. Scope">
            <p>
              This policy applies to the Kondai website, dashboard, APIs,
              customer-care tools and integrations. Connected third-party
              services also have their own privacy policies and permission
              controls.
            </p>
          </PrivacySection>

          <PrivacySection id="data" title="3. Information we collect">
            <h3>Account and workspace information</h3>
            <p>
              Name, email address, business name, role, preferences, account
              identifiers and workspace membership.
            </p>
            <h3>Business information</h3>
            <p>
              Products, pricing, customer segments, campaigns, operational
              notes, uploaded files, support records and other information you
              choose to provide.
            </p>
            <h3>Connected-service information</h3>
            <p>
              Data and technical identifiers permitted by the integrations you
              approve, including OAuth tokens and account identifiers.
            </p>
            <h3>Customer communications</h3>
            <p>
              Message content, sender and recipient details, timestamps,
              attachments, delivery status and conversation metadata when you
              connect a support inbox or WhatsApp Business account.
            </p>
            <h3>Technical information</h3>
            <p>
              IP address, browser and device information, pages viewed, actions,
              error logs, security events and performance information.
            </p>
            <h3>Payment information</h3>
            <p>
              Subscription, invoice and payment-status information from payment
              providers. Kondai does not intentionally store complete payment
              card numbers.
            </p>
          </PrivacySection>

          <PrivacySection id="use" title="4. How we use information">
            <ul>
              <li>Create and manage accounts and workspaces.</li>
              <li>Provide integrations and features you request.</li>
              <li>Generate business insights, recommendations and drafts.</li>
              <li>Organise customer conversations and prepare responses.</li>
              <li>Process actions you approve or otherwise authorise.</li>
              <li>Improve reliability, prevent abuse and provide support.</li>
              <li>Meet legal obligations and enforce agreements.</li>
            </ul>
          </PrivacySection>

          <PrivacySection id="integrations" title="5. Connected services">
            <h3>Meta, Facebook and WhatsApp Business</h3>
            <p>
              Kondai may receive business-account details, WhatsApp Business
              Account IDs, phone-number IDs, business profile information,
              access tokens, customer messages and delivery-status events. We
              use this information to connect the account, route messages to
              the correct workspace, display conversations and send authorised
              messages. Kondai does not ask for your Facebook password.
            </p>
            <h3>Google and Gmail</h3>
            <p>
              With your permission, Kondai may access your Google account email
              address and Gmail information covered by the scopes shown during
              authorisation. With read-only Gmail access, this may include
              message headers, sender and recipient details, subjects,
              timestamps, labels, message content and attachment metadata used
              to identify and organise support messages.
            </p>
            <p>
              Kondai’s use and transfer of information received from Google APIs
              adheres to the Google API Services User Data Policy, including
              Limited Use requirements. We do not use Google user data for
              advertising or sell it.
            </p>
            <h3>GitHub</h3>
            <p>
              Kondai may access your profile, authorised repositories,
              metadata, README files, code structure, languages, commits,
              issues and other resources covered by the permissions you grant.
            </p>
            <h3>Stripe, analytics and product databases</h3>
            <p>
              Kondai may read subscription, invoice and payment status from
              Stripe; analytics from services such as PostHog; and selected
              business records from databases such as Cloud Firestore.
            </p>
            <p>
              You may disconnect an integration from Kondai or revoke access in
              the provider’s account settings. Revocation stops future access,
              but does not automatically erase information already stored.
            </p>
          </PrivacySection>

          <PrivacySection id="ai" title="6. Artificial intelligence">
            <p>
              Kondai uses AI services, including Google Cloud Vertex AI, to
              analyse authorised business information, identify patterns,
              summarise data, prepare recommendations and draft customer
              responses.
            </p>
            <p>
              AI output may be incomplete or inaccurate. Kondai is designed to
              require review or approval before sensitive external actions. You
              remain responsible for reviewing generated content.
            </p>
            <p>
              We do not use customer content to train our own public
              general-purpose AI model.
            </p>
          </PrivacySection>

          <PrivacySection id="sharing" title="7. Sharing">
            <p>We may share information with:</p>
            <ul>
              <li>
                hosting, database, monitoring, analytics, authentication,
                payment and AI providers that operate Kondai;
              </li>
              <li>services you instruct us to connect;</li>
              <li>professional advisers where necessary;</li>
              <li>authorities where legally required;</li>
              <li>
                a buyer or successor during a lawful business transaction.
              </li>
            </ul>
            <p>
              We do not sell personal information or Google user data, and we
              do not share connected-service data with advertisers for targeted
              advertising.
            </p>
          </PrivacySection>

          <PrivacySection id="retention" title="8. Retention">
            <p>
              We retain information only as long as reasonably necessary to
              provide Kondai, maintain records, prevent abuse, resolve disputes
              and meet legal or contractual obligations. Retention periods vary
              by data type. Integration credentials are disabled or deleted
              when a connection is removed, subject to backup cycles and legal
              requirements.
            </p>
          </PrivacySection>

          <PrivacySection id="security" title="9. Security">
            <p>
              We use safeguards such as access controls, encrypted connections,
              restricted production access, encrypted integration credentials,
              logging and backups. No online service can guarantee absolute
              security.
            </p>
          </PrivacySection>

          <PrivacySection id="transfers" title="10. International transfers">
            <p>
              Kondai may use providers outside Zambia. Information may therefore
              be processed in countries with different data-protection laws.
              Where required, we use contractual and organisational safeguards.
            </p>
          </PrivacySection>

          <PrivacySection id="rights" title="11. Your rights">
            <p>Subject to applicable law, you may ask us to:</p>
            <ul>
              <li>confirm whether we process your personal information;</li>
              <li>provide access to information associated with your account;</li>
              <li>correct inaccurate or incomplete information;</li>
              <li>delete information we no longer need to retain;</li>
              <li>restrict or object to certain processing;</li>
              <li>withdraw consent where processing is based on consent;</li>
              <li>provide a portable copy where applicable.</li>
            </ul>
          </PrivacySection>

          <PrivacySection id="deletion" title="12. Data deletion">
            <p>
              Email{" "}
              <a
                href={`mailto:${CONTACT_EMAIL}?subject=Kondai%20Data%20Deletion%20Request`}
              >
                {CONTACT_EMAIL}
              </a>{" "}
              with the subject{" "}
              <strong>“Kondai Data Deletion Request.”</strong>
            </p>
            <p>Include:</p>
            <ul>
              <li>the email address used for your Kondai account;</li>
              <li>your business or workspace name;</li>
              <li>the connected service involved, where relevant;</li>
              <li>a description of the information you want deleted.</li>
            </ul>
            <p>
              We may verify your identity or authority over the workspace.
              Eligible information will then be deleted or anonymised within a
              reasonable period, subject to legal, security, fraud-prevention,
              backup and contractual retention requirements.
            </p>
            <p>
              You may also remove Kondai in Facebook’s “Apps and Websites”
              settings. Removing the app stops future Meta access, but you
              should still contact us to request deletion of information already
              stored in Kondai.
            </p>
          </PrivacySection>

          <PrivacySection id="children" title="13. Children">
            <p>
              Kondai is a business operations service and is not intended for
              children. We do not knowingly create Kondai founder accounts for
              people under 18.
            </p>
          </PrivacySection>

          <PrivacySection id="changes" title="14. Changes">
            <p>
              We may update this policy when our service, integrations or legal
              obligations change. We will publish the revised policy here and
              update the effective date.
            </p>
          </PrivacySection>

          <PrivacySection id="contact" title="15. Contact">
            <address className="privacy-contact">
              <strong>Booxclash Learn LTD</strong>
              <span>Operator of Kondai</span>
              <span>Zambia</span>
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
            </address>
          </PrivacySection>
        </article>
      </div>

      <footer className="privacy-footer">
        <span>© {new Date().getFullYear()} Booxclash Learn LTD</span>
        <a href="/">Return to Kondai</a>
      </footer>
    </main>
  );
}
