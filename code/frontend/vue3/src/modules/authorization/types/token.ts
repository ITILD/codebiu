// src/modules/authorization/types/token.ts

export interface TokenResponseBase {
  token: string;
  expires_in: number;
  token_id: string | null;
}