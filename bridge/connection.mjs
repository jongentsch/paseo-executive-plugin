import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {createPaseoClient} from '@getpaseo/client';

export async function configuredClient(config){
  let authHeader;
  if(config.home){
    try{authHeader=`Bearer ${(await readFile(join(config.home,'local-credential'),'utf8')).trim()}`;}
    catch(error){if(error.code!=='ENOENT')throw error;}
  }
  return createPaseoClient({url:config.url,authHeader,password:config.password||undefined,
    clientId:`hermes-executive-${process.pid}`,connectTimeoutMs:5000,
    reconnect:{enabled:true,baseDelayMs:1000,maxDelayMs:15000}});
}
