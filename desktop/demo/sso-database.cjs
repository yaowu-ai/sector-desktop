// Implements only the SQL used by the original WA SSO adapter. Demo data never leaves memory.
module.exports = function database(users) {
  const attempts=new Map(),links=[];
  const db={links,reset(){attempts.clear();links.length=0;},pool:{query:async(sql,v=[])=>{
    const row=attempts.get(v[0]),valid=row&&row.parent_origin===v[1]&&row.desktop_context===v[2]&&row.expires>Date.now();
    if(sql.startsWith('DELETE FROM hosted_sso_attempts WHERE expires')){
      for(const [key,item]of attempts)if(item.expires<=Date.now())attempts.delete(key);
      return{rows:[],rowCount:0};
    }
    if(sql.startsWith('INSERT INTO hosted_sso_attempts')){
      attempts.set(v[0],{parent_origin:v[1],desktop_context:v[2],attempt_state:'pending',expires:Date.now()+300000});
      return{rows:[],rowCount:1};
    }
    if(sql.includes("SET attempt_state='exchanging'")){
      if(!valid||row.attempt_state!=='pending')return{rows:[],rowCount:0};
      row.attempt_state='exchanging';return{rows:[],rowCount:1};
    }
    if(sql.includes("SET attempt_state='verified'")){
      if(!row||row.attempt_state!=='exchanging'||row.expires<=Date.now())return{rows:[],rowCount:0};
      Object.assign(row,{attempt_state:'verified',identity_issuer:v[1],identity_subject:v[2]});return{rows:[],rowCount:1};
    }
    if(sql.startsWith('SELECT * FROM hosted_sso_attempts'))return{rows:valid&&row.attempt_state==='verified'?[{...row}]:[]};
    if(sql.startsWith('DELETE FROM hosted_sso_attempts'))return{rows:[],rowCount:(v.length===1||valid&&row.attempt_state==='verified')&&attempts.delete(v[0])?1:0};
    if(sql.startsWith('SELECT u.id')){
      const link=links.find(l=>l.identity_issuer===v[0]&&l.identity_subject===v[1]);
      return{rows:link?[users.find(u=>u.id===link.user_id)]:[]};
    }
    if(sql.startsWith('SELECT id FROM hosted_users'))return{rows:users.filter(u=>u.id===v[0]&&!u.disabled)};
    if(sql.startsWith('SELECT * FROM hosted_identity_links'))return{rows:links.filter(l=>l.identity_issuer===v[0]&&l.identity_subject===v[1]||l.user_id===v[2])};
    if(sql.startsWith('INSERT INTO hosted_identity_links')){
      links.push({identity_issuer:v[0],identity_subject:v[1],user_id:v[2]});return{rows:[],rowCount:1};
    }
    throw Error('Unsupported demo SQL');
  }},transaction:fn=>fn(db.pool),withActor:(_user,fn)=>fn()};
  return db;
};
