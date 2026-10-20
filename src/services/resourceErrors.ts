export class ResourceServiceError extends Error {
  readonly status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ResourceServiceError';
    this.status = status;
  }
}
