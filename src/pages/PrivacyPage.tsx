import { LegalLayout, LEGAL_CONTACT_URL } from './LegalLayout';

export default function PrivacyPage() {
  return (
    <LegalLayout title="Privacy Policy">
      <p>
        Stack of Dreams Labs (the "Service") is an experimental project by Sudhir Mishra. This page
        explains what the Service handles when you use it. Access to the AI assistant is by
        invitation only.
      </p>

      <h2>What we collect</h2>
      <ul>
        <li>
          <strong>Account:</strong> the email address your invitation was sent to, and an identifier
          Amazon Cognito assigns to you. Sign-in is handled by Amazon Cognito; the Service never
          sees your password.
        </li>
        <li>
          <strong>Your questions to the assistant and your searches:</strong> the text you type and
          the ZIP code you search. It is sent to AWS services to produce an answer (see below).
        </li>
        <li>
          <strong>Usage counters:</strong> how many requests and estimated tokens each account has
          used, so daily and monthly limits can be enforced. Counters are deleted automatically
          after about 35 days (daily) and 70 days (monthly).
        </li>
        <li>
          <strong>Operational logs:</strong> technical records such as timing, status codes and
          error types. The Service is built so that message text is not written to its logs.
        </li>
      </ul>

      <h2>What we do not do</h2>
      <ul>
        <li>No advertising, tracking pixels or analytics cookies.</li>
        <li>We do not sell or share your information for marketing.</li>
        <li>
          Your access token is kept in your browser's memory only and is cleared when you close or
          reload the tab.
        </li>
      </ul>

      <h2>Who processes your data</h2>
      <p>
        The Service runs on Amazon Web Services in the United States. Your questions are processed
        by Amazon Bedrock (Amazon Nova models) through Amazon Bedrock AgentCore. Map tiles and
        distances come from Amazon Location Service. Hosting is by AWS Amplify. These providers
        process data under their own terms.
      </p>

      <h2>Where the directory data comes from</h2>
      <p>
        Provider information shown in search results comes from OpenStreetMap (© OpenStreetMap
        contributors, ODbL) and NYC Open Data. It is community-sourced, labelled unverified, and may
        be out of date. Inventory figures marked "demo" are fictional samples.
      </p>

      <h2>Please do not enter sensitive information</h2>
      <p>
        This is an experimental demo. Do not enter health, financial, immigration or other sensitive
        personal information, or details that identify other people, into the assistant.
      </p>

      <h2>Your choices</h2>
      <p>
        You can ask to have your account and its usage counters deleted, or ask a question about
        this policy, through the contact page below. Because this is a small pilot, requests are
        handled by hand.
      </p>

      <h2>Changes</h2>
      <p>If this policy changes, the date at the top will change.</p>

      <h2>Contact</h2>
      <p>
        <a className="text-fg underline underline-offset-4" href={LEGAL_CONTACT_URL}>
          sudhirmishra.in
        </a>
      </p>
    </LegalLayout>
  );
}
