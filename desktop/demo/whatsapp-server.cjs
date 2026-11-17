// Loopback-only fixture serving the ORIGINAL hosted assets and workspace model.
// No worker, network adapter, database or real WhatsApp session is started.
const http = require('node:http');
const path = require('node:path');
const {randomUUID, randomBytes} = require('node:crypto');
const waRoot = process.env.WA_MANAGER_ROOT || path.resolve(__dirname, '../../../h-wa-account-manager');
const {publicAssets} = require(path.join(waRoot, 'src/hosted/public-assets.cjs'));
const {HostedWorkspace} = require(path.join(waRoot, 'src/hosted/workspace.cjs'));
const {vault} = require(path.join(waRoot, 'src/hosted/crypto.cjs'));
const {sessionToken} = require(path.join(waRoot, 'src/hosted/embed-policy.cjs'));
const {AccountMatrixSso} = require(path.join(waRoot, 'src/hosted/account-matrix-sso.cjs'));
const social = require(path.join(waRoot, 'src/hosted/social.cjs'));
const chatTemplates = require(path.join(waRoot, 'src/hosted/chat-templates.cjs'));
process.env.TZ = 'Asia/Shanghai';
const config = {embedOrigins: ['http://127.0.0.1:1420', 'http://localhost:1420']};
const serve = publicAssets(waRoot, config), sessions = new Map();
const store = HostedWorkspace.load(null, '', vault(randomBytes(32).toString('hex')));
const workspaceId = randomUUID(), user = {id: randomUUID(), name:'演示运营员', role:'admin',email:'demo@account-matrix.local'};
const users=[user,{id:randomUUID(),name:'演示观察员',role:'viewer',email:'viewer@account-matrix.local'}];
for(const item of users)Object.assign(item,{org_id:workspaceId,disabled:false});
const db=require('./sso-database.cjs')(users);
const sso=new AccountMatrixSso(db,{exchangeUrl:'http://127.0.0.1:8790/api/desktop/whatsapp/exchange',
  issuer:'http://127.0.0.1:8790',workspaceOrigin:'http://127.0.0.1:8789',secret:'demo-service-secret-not-for-production-12345'});
const workspaces = [{id:workspaceId, workspaceName:'WhatsApp 运营空间 · 示例', memberRole:'admin'}];
const connections = {};
for (const [index, name] of ['雅加达 · 运营 01','雅加达 · 运营 02','上海 · 客服 01','新账号 · 待连接'].entries()) {
  const account = store.account({name, provider:'baileys', group:index < 2 ? '印尼运营组' : '客户服务组'});
  if (index < 3) {
    account.number = `1555000010${index}`;
    connections[account.id] = {status:'online', ready:true, authenticated:true, sessionSavedAt:Date.now(), connectedAt:Date.now()-86400000};
  }
}
const rule = store.data.rules[0];
rule.name = '7 天基础预热 · 中文';
const task = store.task({name:'运营账号 · 日常互聊', ruleId:rule.id, accountIds:store.data.accounts.slice(0,2).map(a=>a.id)});
Object.assign(task, {status:'running', startedAt:Date.now()-86400000, ruleSnapshot:structuredClone(rule)});
store.task({name:'客服账号 · 基础预热', ruleId:rule.id, accountIds:store.data.accounts.slice(2,4).map(a=>a.id)});
for (let i=0;i<12;i++) store.data.logs.push({
  id:randomUUID(), taskId:task.id, senderId:store.data.accounts[i%2].id, receiverId:store.data.accounts[(i+1)%2].id,
  peer:store.data.accounts[(i+1)%2].number, at:Date.now()-i*300000, status:'submitted',
  delivery:i<8?'read':'delivered', messageId:`demo-${i}`, body:['今天的工作安排好了吗？','已经安排好了，下午一起确认一下。'][i%2],
});
function snapshot(actor=user) {
  return {...store.snapshot(), workspaceId, orgName:workspaces[0].workspaceName, workspaces:workspaces.map(w=>({...w,memberRole:actor.role})), user:actor, email:actor.email,
    connections, incidents:[], proxyUsage:[], members:actor.role==='admin'?users:[], nodes:[],
    taskStages:Object.fromEntries(store.data.tasks.map(t=>[t.id,{day:2}])),
    runtime:{hosted:true,providers:['baileys'],version:'0.7.0 · 交互演示',build:{builtAt:'本地示例'},adapter:'示例数据',timezone:'Asia/Shanghai',dataDirectory:'内存示例',executable:'演示模式'},
    hubState:null,hubError:'',hostedHub:''};
}
function send(res,status,headers,body) {res.writeHead(status,headers);res.end(body);}
const json = (res,status,value) => send(res,status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'},JSON.stringify(value));
const server = http.createServer(async(req,res)=>{
  res.setHeader('X-Frame-Options','DENY');
  try {
    const url = new URL(req.url,'http://127.0.0.1:8789');
    if(req.method==='GET'&&url.pathname==='/demo/status')return json(res,200,{sessions:sessions.size,bindings:db.links.length});
    if(config.embedOrigins.includes(req.headers.origin)){
      res.setHeader('Access-Control-Allow-Origin',req.headers.origin);res.setHeader('Access-Control-Allow-Methods','POST,OPTIONS');
    }
    if(req.method==='OPTIONS')return send(res,204,{},'');
    if(req.method==='POST'&&url.pathname==='/demo/reset'&&config.embedOrigins.includes(req.headers.origin)){
      db.reset();sessions.clear();return json(res,200,{ok:true});
    }
    if(req.method==='POST'&&url.pathname==='/demo/expire'&&config.embedOrigins.includes(req.headers.origin)){
      sessions.clear();return json(res,200,{ok:true});
    }
    if (req.method==='GET' && serve(req,res,url,send)) return;
    if (req.method!=='POST'||url.pathname!=='/api/command') return json(res,404,{ok:false,error:'演示接口不存在'});
    if (req.headers.origin!=='http://127.0.0.1:8789') return json(res,403,{ok:false,error:'来源无效'});
    let raw=''; for await (const chunk of req) {raw+=chunk;if(raw.length>1024*1024)throw Error('演示内容过大');}
    const {command,data={}}=JSON.parse(raw), token=sessionToken(req,config), actor=sessions.get(token),authenticated=!!actor;
    const currentSnapshot=()=>snapshot(actor);
    if(command==='bootstrap')return json(res,200,{ok:true,data:{hosted:true,hasUser:true,accountMatrixSso:true,authenticated,email:actor?.email||'',csrf:authenticated?'demo-csrf':'',workspaceId,workspaces,...(authenticated&&data.includeSnapshot?{snapshot:currentSnapshot()}:{})}});
    if(['ssoStart','ssoLogin','ssoBind'].includes(command)){
      const parent=req.headers['x-account-matrix-parent'],params={parent,context:data.context,nonce:data.nonce,ticket:data.ticket};
      if(!config.embedOrigins.includes(parent))return json(res,403,{ok:false,error:'来源无效'});
      if(command==='ssoStart')return json(res,200,{ok:true,data:await sso.start(parent,data.context)});
      let target;
      if(command==='ssoLogin'){
        const result=await sso.login(params);
        if(result.bindingRequired)return json(res,200,{ok:true,data:{bindingRequired:true}});
        target=result.user;
      }else{
        target=users.find(u=>u.email===data.email);
        if(!target||data.password!=='DemoOnly2026!')return json(res,401,{ok:false,error:'演示密码为 DemoOnly2026!，请使用对应的演示邮箱'});
        await sso.bind({...params,user:target});
      }
      const next=randomBytes(32).toString('base64url');sessions.set(next,target);
      return json(res,200,{ok:true,embedSession:next,data:snapshot(target)});
    }
    if(!authenticated)return json(res,401,{ok:false,error:'请登录演示空间'});
    if(req.headers['x-csrf-token']!=='demo-csrf')return json(res,403,{ok:false,error:'请求校验失败'});
    if(command==='logout'){sessions.delete(token);return json(res,200,{ok:true});}
    if(command==='workspaces')return json(res,200,{ok:true,data:{workspaces}});
    if(command==='snapshot')return json(res,200,{ok:true,data:currentSnapshot()});
    if(command==='preview')return json(res,200,{ok:true,data:store.preview(data,id=>connections[id]?.ready)});
    if(command==='weeklyScripts'){
      const library=chatTemplates.library(data.templateId);
      return json(res,200,{ok:true,data:data.day===undefined?library:library[data.channel][data.day]});
    }
    if(command==='historyPage')return json(res,200,{ok:true,data:{rows:[],next:null}});
    if(actor.role==='viewer')return json(res,403,{ok:false,error:'观察员无权修改工作空间'});
    if(command==='socialCreate'){social.createRun(store,connections,data);return json(res,200,{ok:true,data:currentSnapshot()});}
    if(command==='socialStop'){social.stop(store,data.id);return json(res,200,{ok:true,data:currentSnapshot()});}
    if(command==='weeklyResume'){social.resume(store,connections,data.id);return json(res,200,{ok:true,data:currentSnapshot()});}
    if(command==='account'){const item=store.account(data);return json(res,200,{ok:true,data:{...currentSnapshot(),savedId:item.id}});}
    if(command==='task'){const item=store.task(data);return json(res,200,{ok:true,data:{...currentSnapshot(),savedId:item.id}});}
    if(command==='taskStatus')store.taskStatus(data.id,data.status);
    else if(command==='rule')store.rule(data);
    else if(command==='note')store.note(data);
    else if(command==='pauseAccount')store.data.health[data.id]={held:true,reason:'演示中手动暂停'};
    else if(command==='releaseAccount')store.data.health[data.id]={held:false};
    else if(command==='remove')store.remove(data.collection,data.id);
    else return json(res,400,{ok:false,error:'交互演示未启用此操作，不会连接或发送真实消息。'});
    json(res,200,{ok:true,data:currentSnapshot()});
  } catch(error){json(res,400,{ok:false,error:error.message});}
});
server.listen(8789,'127.0.0.1',()=>console.log('Original WA webpage demo: http://127.0.0.1:8789'));
