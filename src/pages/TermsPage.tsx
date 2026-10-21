import { LegalLayout, LEGAL_CONTACT_URL } from './LegalLayout';

export default function TermsPage() {
  return (
    <LegalLayout title="Terms of Service">
      <p>
        These terms apply to Stack of Dreams Labs and the Community Resource Navigator (the
        "Service"), an experimental project by Sudhir Mishra. By signing in or using the Service you
        agree to them.
      </p>

      <h2>Invitation-only pilot</h2>
      <p>
        Use of the AI assistant is limited to invited users. Accounts are personal; do not share
        your sign-in. Usage limits apply (for example, a daily and monthly number of assistant
        requests) and may change or be switched off at any time without notice.
      </p>

      <h2>Not professional or emergency advice</h2>
      <p>
        The Service helps you look up community resources such as food assistance. Information may
        be incomplete, out of date or wrong. Provider details come from community-sourced and public
        data and are not verified. Always confirm hours, location and availability with the provider
        before you travel. In an emergency, call your local emergency number.
      </p>

      <h2>AI-generated answers</h2>
      <p>
        Answers are produced by an AI model using the directory data the Service retrieves. They can
        contain mistakes. Inventory for real providers is not known to the Service; figures labelled
        "demo" are fictional.
      </p>

      <h2>Acceptable use</h2>
      <ul>
        <li>
          Do not attempt to bypass limits, probe or disrupt the Service, or access other users'
          data.
        </li>
        <li>
          Do not use the Service for anything unlawful, or to submit sensitive personal information.
        </li>
        <li>Do not use automated tools to send requests at scale.</li>
      </ul>

      <h2>Data and third-party content</h2>
      <p>
        How your information is handled is described in the{' '}
        <a className="text-fg underline underline-offset-4" href="/privacy">
          Privacy Policy
        </a>
        . Directory data © OpenStreetMap contributors (ODbL) and NYC Open Data, used under their
        licences.
      </p>

      <h2>No warranty; limitation of liability</h2>
      <p>
        The Service is provided "as is" and "as available" for demonstration, without warranties of
        any kind. To the extent the law allows, the owner is not liable for any loss arising from
        your use of, or reliance on, the Service.
      </p>

      <h2>Changes and termination</h2>
      <p>
        The Service or these terms may change, and access may be suspended or ended at any time. The
        date at the top shows the latest version.
      </p>

      <h2>Contact</h2>
      <p>
        <a className="text-fg underline underline-offset-4" href={LEGAL_CONTACT_URL}>
          sudhirmishra.in
        </a>
      </p>
    </LegalLayout>
  );
}
