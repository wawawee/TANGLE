import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Bot, User, Loader2, Sparkles, Shield, Flame, Activity, GripVertical, X, Minimize2, Maximize2 } from 'lucide-react';
import { agentChat } from '../../services/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface AgentChatProps {
  isOpen: boolean;
  onClose: () => void;
  initialAgent?: string;
}

type Agent = 'orchestrator' | 'sunny' | 'devils_advocate' | 'architect' | 'omega';

const AGENTS: Record<Agent, { name: string; icon: React.ReactNode; greeting: string }> = {
  orchestrator: {
    name: 'The Orchestrator',
    icon: <Shield size={14} />,
    greeting: "I'm The Orchestrator - I coordinate the agent swarm. How can I help you today?"
  },
  sunny: {
    name: 'Sunny',
    icon: <Sparkles size={14} />,
    greeting: "Hey there! I'm Sunny - always looking on the bright side! What's on your mind?"
  },
  devils_advocate: {
    name: "Devil's Advocate",
    icon: <Flame size={14} />,
    greeting: "I'm the Devil's Advocate. I question everything. What supposedly brilliant idea do you want me to pick apart?"
  },
  architect: {
    name: 'The Architect',
    icon: <Bot size={14} />,
    greeting: "I am The Architect - your system observer. I can analyze your agent swarm and suggest improvements."
  },
  omega: {
    name: 'Omega',
    icon: <Activity size={14} />,
    greeting: "I'm Omega. The Caretaker. I watch the watchers. I've seen every error. Want me to check the system?"
  }
};

export const AgentChat: React.FC<AgentChatProps> = ({ isOpen, onClose, initialAgent = 'orchestrator' }) => {
  const [activeAgent, setActiveAgent] = useState<Agent>(initialAgent as Agent);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  const [position, setPosition] = useState({ x: 20, y: 20 });
  const [size, setSize] = useState({ width: 560, height: 520 });
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const resizeStart = useRef({ x: 0, y: 0, width: 0, height: 0 });

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatRef = useRef<HTMLDivElement>(null);

  const agent = AGENTS[activeAgent];

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.resize-handle') || (e.target as HTMLElement).closest('button') || (e.target as HTMLElement).closest('input')) return;
    setIsDragging(true);
    dragOffset.current = { x: e.clientX - position.x, y: e.clientY - position.y };
  }, [position]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (isDragging) {
      setPosition({ x: e.clientX - dragOffset.current.x, y: e.clientY - dragOffset.current.y });
    }
    if (isResizing) {
      const newWidth = Math.max(300, Math.min(600, resizeStart.current.width + (e.clientX - resizeStart.current.x)));
      const newHeight = Math.max(300, Math.min(800, resizeStart.current.height + (e.clientY - resizeStart.current.y)));
      setSize({ width: newWidth, height: newHeight });
    }
  }, [isDragging, isResizing]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    setIsResizing(false);
  }, []);

  useEffect(() => {
    if (isDragging || isResizing) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, isResizing, handleMouseMove, handleMouseUp]);

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setIsResizing(true);
    resizeStart.current = { x: e.clientX, y: e.clientY, width: size.width, height: size.height };
  }, [size]);

  useEffect(() => {
    if (isOpen) {
      setMessages([{
        id: '1',
        role: 'assistant',
        content: agent.greeting,
        timestamp: new Date()
      }]);
    }
  }, [isOpen, activeAgent]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await agentChat(activeAgent, input.trim());

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.result || response.response || 'No response',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      ref={chatRef}
      className="fixed flex flex-col z-[99999]"
      style={{
        left: position.x,
        top: position.y,
        width: size.width,
        height: isMinimized ? 'auto' : size.height,
        border: '3px solid #333',
        backgroundColor: '#0a0a0a',
        boxShadow: '8px 8px 0px 0px rgba(0,0,0,0.4)',
      }}
    >
      <div
        onMouseDown={handleMouseDown}
        className="flex items-center gap-2 px-3 py-2 cursor-move border-b-2 border-[#333] bg-[#111]"
      >
        <GripVertical size={14} className="text-[#555]" />

        <div className="flex gap-1 flex-1 overflow-x-auto">
          {(Object.keys(AGENTS) as Agent[]).map((a) => (
            <button
              key={a}
              onClick={() => { setActiveAgent(a); setMessages([{ id: '1', role: 'assistant', content: AGENTS[a].greeting, timestamp: new Date() }]); }}
              className={`px-2 py-1 text-[10px] font-bold uppercase tracking-wider transition-colors whitespace-nowrap flex items-center gap-1 ${
                activeAgent === a
                  ? 'bg-white text-black'
                  : 'bg-transparent text-[#555] hover:text-white border border-transparent hover:border-[#444]'
              }`}
            >
              {AGENTS[a].icon}
              <span className="hidden sm:inline">{AGENTS[a].name}</span>
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="p-1 hover:bg-[#222] transition-colors rounded-none"
          >
            {isMinimized ? <Maximize2 size={12} className="text-gray-500" /> : <Minimize2 size={12} className="text-gray-500" />}
          </button>
          <button
            onClick={onClose}
            className="p-1 hover:bg-[#ff003c] hover:text-white transition-colors rounded-none"
          >
            <X size={14} className="text-gray-500 hover:text-white" />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          <div className="flex items-center justify-between px-4 py-2 border-b-2 border-[#222] bg-[#0f0f0f]">
            <div className="flex items-center gap-2">
              <span className="text-gray-400">{agent.icon}</span>
              <span className="text-sm font-bold uppercase tracking-wider text-white">{agent.name}</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#00ff88] animate-pulse" />
              <span className="text-[10px] font-mono text-gray-600 uppercase">Online</span>
            </div>
          </div>

          <div
            className="flex-1 overflow-y-auto p-4 space-y-3"
            style={{
              height: size.height - 140,
              scrollbarWidth: 'thin',
              scrollbarColor: '#333 #111',
              overflowY: 'auto'
            }}
          >
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] p-3 text-sm ${
                    msg.role === 'user'
                      ? 'bg-white text-black border-2 border-white'
                      : 'bg-[#111] text-gray-200 border-2 border-[#333]'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    {msg.role === 'user' ? (
                      <User size={11} className="text-black" />
                    ) : (
                      <span className="text-gray-400">{agent.icon}</span>
                    )}
                    <span className="text-[9px] font-bold uppercase tracking-wider text-gray-500">
                      {msg.role === 'user' ? 'You' : agent.name}
                    </span>
                  </div>
                  <p className="whitespace-pre-wrap leading-relaxed font-mono text-xs">{msg.content}</p>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-[#111] border-2 border-[#333] p-3 flex items-center gap-2">
                  <Loader2 size={12} className="animate-spin text-gray-400" />
                  <span className="text-xs font-mono text-gray-500 uppercase">Thinking...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="p-3 border-t-2 border-[#222] bg-[#0f0f0f]">
            <div className="flex gap-2 items-center">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={`Message ${agent.name.split(' ')[0]}...`}
                disabled={isLoading}
                className="flex-1 bg-[#111] border-2 border-[#333] px-4 py-2.5 text-sm text-white placeholder-gray-600 font-mono focus:outline-none focus:border-white transition-colors"
              />
              <button
                onClick={handleSend}
                disabled={isLoading || !input.trim()}
                className="px-4 py-2.5 border-2 border-[#333] bg-[#111] text-white hover:bg-white hover:text-black hover:border-white transition-all disabled:opacity-30 disabled:cursor-not-allowed font-mono text-xs uppercase tracking-wider font-bold"
              >
                <Send size={14} />
              </button>
            </div>
          </div>

          <div
            className="resize-handle absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
            onMouseDown={handleResizeStart}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" className="absolute bottom-2 right-2 text-gray-600">
              <path d="M10 0L0 10M10 4L4 10M10 8L8 10" stroke="currentColor" strokeWidth="1.5" fill="none" />
            </svg>
          </div>
        </>
      )}
    </div>
  );
};

export default AgentChat;
