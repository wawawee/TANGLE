import { Calendar, CheckCircle2, Mail, Phone, Send } from 'lucide-react';
import { useState } from 'react';

export default function ChatBox() {
  const [messages, setMessages] = useState([
    { id: 1, text: 'Analysis complete. Strategy solidified. Shall we proceed?', type: 'ai' }
  ]);
  const [input, setInput] = useState('');
  const [showActions, setShowActions] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const handleSend = () => {
    if (!input.trim()) return;
    setMessages([...messages, { id: Date.now(), text: input, type: 'user' }]);
    setInput('');
    setTimeout(() => {
      setMessages(prev => [...prev, { id: Date.now() + 1, text: 'Acknowledged. Would you like to distribute the summary?', type: 'ai' }]);
      setShowActions(true);
    }, 1000);
  };

  const executeAction = (name: string) => {
    setStatus(`Executing: ${name}...`);
    setTimeout(() => {
      setStatus(`${name} Sent! ✅`);
      setTimeout(() => setStatus(null), 3000);
    }, 2000);
  };

  return (
    <div className="fixed bottom-6 right-6 w-80 glass rounded-3xl overflow-hidden shadow-2xl z-[100] border border-white/40 flex flex-col max-h-[500px]">
      {/* Header */}
      <div className="px-4 py-3 bg-white/40 backdrop-blur-md border-b border-black/5 flex items-center justify-between">
        <span className="text-xs font-black tracking-widest text-slate-800 uppercase">Strategist Chat</span>
        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
      </div>

      {/* Messages */}
      <div className="flex-1 p-4 space-y-3 overflow-y-auto">
        {messages.map(m => (
          <div key={m.id} className={`flex ${m.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] px-3 py-2 rounded-2xl text-[11px] font-medium leading-relaxed ${
              m.type === 'user' ? 'bg-purple-600 text-white rounded-br-none' : 'bg-white/60 text-slate-700 rounded-bl-none border border-black/5'
            }`}>
              {m.text}
            </div>
          </div>
        ))}
        {showActions && !status && (
          <div className="grid grid-cols-1 gap-2 animate-in fade-in slide-in-from-bottom-2 duration-500">
            <button onClick={() => executeAction('Email')} className="flex items-center gap-2 px-3 py-2 bg-white/80 hover:bg-white rounded-xl border border-black/5 text-[10px] font-bold text-slate-600 transition-all">
              <Mail size={14} className="text-cyan-500" /> Send Email Summary
            </button>
            <button onClick={() => executeAction('Meeting')} className="flex items-center gap-2 px-3 py-2 bg-white/80 hover:bg-white rounded-xl border border-black/5 text-[10px] font-bold text-slate-600 transition-all">
              <Calendar size={14} className="text-purple-500" /> Book Strategy Meeting
            </button>
            <button onClick={() => executeAction('Call')} className="flex items-center gap-2 px-3 py-2 bg-white/80 hover:bg-white rounded-xl border border-black/5 text-[10px] font-bold text-slate-600 transition-all">
              <Phone size={14} className="text-emerald-500" /> Initiate Feedback Call
            </button>
          </div>
        )}
        {status && (
          <div className="flex items-center gap-2 bg-emerald-50 text-emerald-700 px-3 py-2 rounded-xl border border-emerald-100 text-[10px] font-bold animate-in zoom-in duration-300">
            <CheckCircle2 size={14} /> {status}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-3 bg-white/20 border-t border-black/5">
        <div className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Talk to TANGLE..."
            className="w-full bg-white/60 border border-black/5 rounded-xl px-3 py-2 text-[10px] focus:outline-none focus:ring-2 focus:ring-purple-400 transition-all"
          />
          <button onClick={handleSend} className="absolute right-2 top-1.5 p-1 text-purple-600 hover:text-purple-800 transition-all">
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
