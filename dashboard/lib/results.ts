import { env } from 'cloudflare:workers';
import seed from './seed.json';
export async function database(){
 const db=env.DB; if(!db) throw new Error('Database binding unavailable');
 const existing=await db.prepare('SELECT run_id FROM analyses WHERE run_id=?').bind(seed.runId).first();
 if(!existing){
  for(let i=0;i<seed.reviews.length;i+=25){ await db.batch(seed.reviews.slice(i,i+25).map(r=>db.prepare('INSERT OR IGNORE INTO reviews (key,run_id,review_id,payload) VALUES(?,?,?,?)').bind(seed.runId+':'+r.review_id,seed.runId,r.review_id,JSON.stringify(r)))); }
  await db.prepare('INSERT OR IGNORE INTO analyses (run_id,payload) VALUES(?,?)').bind(seed.runId,JSON.stringify(seed.analysis)).run();
 }
 return db;
}
export const runId=seed.runId;
