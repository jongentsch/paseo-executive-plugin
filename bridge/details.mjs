import {createInterface} from 'node:readline';
import {configuredClient} from './connection.mjs';
import {readActivity} from './activity.mjs';

const input=createInterface({input:process.stdin});
const config=JSON.parse(await new Promise(resolve=>input.once('line',resolve)));
input.close();
let client;
try{
  client=await configuredClient(config);
  await client.connect();
  const activity=await readActivity(client,config.agent_id,{limit:config.tail,turnId:config.turn_id,updatedAt:config.updated_at});
  process.stdout.write(JSON.stringify(activity)+'\n');
}catch(error){process.stdout.write(JSON.stringify({source:'paseo_sdk_timeline',error:String(error)})+'\n');process.exitCode=1;}
finally{if(client)await client.close();}
