export interface AuthUser {
  id: string;
  email?: string;
  name?: string;
}

/** none = public app (default); mock = fake local sign-in; oidc = Amazon Cognito / any OIDC provider. */
export type AuthMode = 'none' | 'mock' | 'oidc';

export interface AuthService {
  readonly mode: AuthMode;
  /** Restores an existing session, if any. Resolves to null when signed out. */
  init(): Promise<AuthUser | null>;
  /** Starts sign-in. `returnTo` is an in-app path to return to afterwards. */
  signIn(returnTo?: string): Promise<AuthUser | null | void>;
  /** Finishes a redirect-based sign-in on the callback route. Resolves with the return path. */
  completeSignIn(): Promise<{ user: AuthUser; returnTo: string }>;
  signOut(): Promise<void>;
  /** A valid access token for the API, or null when not signed in. */
  getAccessToken(): Promise<string | null>;
}
