import "dotenv/config";
import { runIngest } from "../src/lib/ingest/run";

runIngest().then(() => process.exit(0), (e) => { console.error(e); process.exit(1); });
