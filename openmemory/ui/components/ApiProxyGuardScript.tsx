/**
 * Rewrites stale cached bundles that still call Docker-internal API hosts
 * (openmemory-mcp / openmemory-api:8765) to same-origin /api-proxy.
 * Inline in the root layout so it runs before any webpack chunk (HTML is no-store).
 */
export function ApiProxyGuardScript() {
  const script = `(function(){var B=/^(openmemory-mcp|openmemory-api|openmemory_mcp)$/i;function rw(u){try{if(typeof u!=="string"||u.indexOf("/api-proxy")===0)return u;var p=new URL(u,location.origin);if(B.test(p.hostname)||(p.port==="8765"&&p.origin!==location.origin))return"/api-proxy"+p.pathname+p.search;}catch(e){}return u;}var f=fetch;fetch=function(i,o){if(typeof i==="string")return f(rw(i),o);if(i&&i.url){var n=rw(i.url);if(n!==i.url)return f(new Request(n,i),o);}return f(i,o);};var xo=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(m,u){return xo.apply(this,[m,rw(String(u))].concat([].slice.call(arguments,2)));};})();`;

  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
