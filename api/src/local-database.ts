import { neonConfig } from "@neondatabase/serverless";

const LOCAL_DATABASE_HOST = "db.localtest.me";
const LOCAL_SQL_ENDPOINT = "http://127.0.0.1:4444/sql";

export function useLocalDatabaseWhenAsked(databaseUrl: string): void {
  if (new URL(databaseUrl).hostname === LOCAL_DATABASE_HOST) neonConfig.fetchEndpoint = LOCAL_SQL_ENDPOINT;
}
