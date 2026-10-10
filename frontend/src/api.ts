import type {Approval,Benchmark,CaseDetail,Communication,Incident,LedgerEvent,RecoveryCase,Summary} from "./types";
const BASE_URL=import.meta.env.VITE_API_URL??"http://localhost:8000/api/v1";
let token=localStorage.getItem("revive_token");
export const setToken=(value:string|null)=>{token=value;if(value)localStorage.setItem("revive_token",value);else localStorage.removeItem("revive_token")};
export const hasToken=()=>Boolean(token);
async function request<T>(path:string,init?:RequestInit):Promise<T>{
 const headers:Record<string,string>={"Content-Type":"application/json",...(init?.headers as Record<string,string>??{})};if(token)headers.Authorization=`Bearer ${token}`;
 const response=await fetch(`${BASE_URL}${path}`,{...init,headers});
 if(response.status===401){setToken(null);window.dispatchEvent(new Event("revive:session-expired"));throw new Error("Your session expired. Please sign in again.")}
 if(!response.ok)throw new Error(`${response.status}: ${await response.text()}`);return response.json() as Promise<T>;
}
export const api={
 login:(email:string,password:string)=>request<{access_token:string;role:string}>("/auth/login",{method:"POST",body:JSON.stringify({email,password})}),
 summary:()=>request<Summary>("/dashboard/summary"),cases:()=>request<RecoveryCase[]>("/cases"),incidents:()=>request<Incident[]>("/incidents"),caseDetail:(id:string)=>request<CaseDetail>(`/cases/${id}`),
 benchmark:(count=1000,seed=2026)=>request<Benchmark>("/simulations/run",{method:"POST",body:JSON.stringify({count,seed})}),judge:()=>request<{seeded:unknown;benchmark:Benchmark;demo_mode:string}>("/demo/judge",{method:"POST"}),seed:(count=30,seed=42)=>request("/demo/seed",{method:"POST",body:JSON.stringify({count,seed})}),
 approve:(id:string)=>request(`/cases/${id}/approve`,{method:"POST"}),reject:(id:string,reason:string)=>request(`/cases/${id}/reject`,{method:"POST",body:JSON.stringify({reason})}),approvals:()=>request<Approval[]>("/approvals"),
 promise:(id:string,promised_date:string,source_message:string)=>request(`/cases/${id}/promise-to-pay`,{method:"POST",body:JSON.stringify({promised_date,source_message,confidence:.95})}),reconcile:(id:string)=>request(`/cases/${id}/reconcile`,{method:"POST"}),stop:(id:string)=>request(`/cases/${id}/stop`,{method:"POST",body:JSON.stringify({reason:"operator_stopped"})}),
 communications:()=>request<Communication[]>("/communications"),ledger:()=>request<LedgerEvent[]>("/ledger"),verifyLedger:()=>request<{valid:boolean;case_count:number;event_count:number;violations:number}>("/ledger/verify"),
};
