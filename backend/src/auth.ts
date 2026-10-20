import { CognitoJwtVerifier } from 'aws-jwt-verify';

export interface VerifiedUser {
  sub: string;
}

/** Verifies a bearer token and returns the user, or null when it is missing/invalid. */
export type TokenVerifier = (authorizationHeader: string | undefined) => Promise<VerifiedUser | null>;

export function createCognitoVerifier(userPoolId: string, clientId: string): TokenVerifier {
  type Verifier = ReturnType<typeof CognitoJwtVerifier.create<{ userPoolId: string; tokenUse: 'access'; clientId: string }>>;
  let verifier: Verifier | undefined;

  return async (header) => {
    const match = /^Bearer\s+(\S+)$/i.exec(header ?? '');
    if (!match) return null;
    try {
      // Created lazily so a misconfiguration fails closed (401) instead of crashing at import.
      // Checks signature (JWKS fetched from the pool and cached), issuer, expiry, token_use and client_id.
      verifier ??= CognitoJwtVerifier.create({ userPoolId, tokenUse: 'access', clientId });
      const payload = await verifier.verify(match[1]);
      return typeof payload.sub === 'string' && payload.sub ? { sub: payload.sub } : null;
    } catch (err) {
      if (!userPoolId || !clientId) console.error('Cognito verifier is not configured', err);
      return null;
    }
  };
}
