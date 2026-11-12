export type Keys = Record<string, string>;
export type VerifyCode = "ok" | "malformed" | "tampered" | "unknown_key" | "key_mismatch" | "bad_signature" | "unsupported";
export interface VerifyResult {
  valid: boolean;
  code: VerifyCode;
  reason: string;
  digest?: string;
  subject?: string;
  certId?: string;
  issuedAt?: string;
  claims?: number;
  note?: string;
}
export function canonicalJson(v: unknown): string;
export function digestOf(payload: unknown): Promise<string>;
export function keyId(publicKeyB64Url: string): Promise<string>;
export function verifySignature(digestHex: string, signatureB64Url: string, publicKeyB64Url: string): Promise<boolean>;
export function verifyCertificate(cert: unknown, keys: Keys): Promise<VerifyResult>;
export function fromHex(h: string): Uint8Array;
export function fromB64Url(s: string): Uint8Array;
export function leafHash(entryBytes: Uint8Array): Promise<Uint8Array>;
export function verifyInclusion(leaf: Uint8Array, index: number, size: number, proof: Uint8Array[], root: Uint8Array): Promise<boolean>;
export function verifyConsistency(first: number, second: number, firstRoot: Uint8Array, secondRoot: Uint8Array, proof: Uint8Array[]): Promise<boolean>;
export function verifyCheckpoint(
  cp: { text: string; signature: string; key_id: string },
  keys: Keys,
): Promise<{ valid: boolean; reason?: string; size?: number; root?: string }>;
