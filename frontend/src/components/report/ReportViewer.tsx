import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ReportViewerProps {
  deliverables: any;
}

export function ReportViewer({ deliverables }: ReportViewerProps) {
  if (!deliverables) return null;

  return (
    <div className="h-full overflow-y-auto p-6 space-y-8 text-[#111]">
      <div className="prose prose-sm max-w-none font-mono">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {deliverables.strategic_report || 'No report available.'}
        </ReactMarkdown>
      </div>

      {deliverables.emails && deliverables.emails.length > 0 && (
        <div className="space-y-4 pt-6 border-t-4 border-[#111]">
          <h3 className="text-lg font-black uppercase">Pre-written Emails</h3>
          {deliverables.emails.map((email: any, idx: number) => (
            <div key={idx} className="bg-[#f4f4f0] p-4 border-2 border-[#111]">
              <div className="text-sm font-bold uppercase mb-2 border-b-2 border-[#111] pb-2">Subject: {email.subject}</div>
              <div className="text-sm whitespace-pre-wrap font-mono">{email.body}</div>
            </div>
          ))}
        </div>
      )}

      {deliverables.contacts && deliverables.contacts.length > 0 && (
        <div className="space-y-4 pt-6 border-t-4 border-[#111]">
          <h3 className="text-lg font-black uppercase">Contact List</h3>
          <div className="grid grid-cols-1 gap-4">
            {deliverables.contacts.map((contact: any, idx: number) => (
              <div key={idx} className="flex items-center justify-between bg-[#f4f4f0] p-4 border-2 border-[#111]">
                <div>
                  <div className="font-black uppercase">{contact.name}</div>
                  <div className="text-xs font-mono">{contact.role} • {contact.organization}</div>
                </div>
                <div className="flex space-x-2">
                  {contact.contact_methods?.map((method: string, mIdx: number) => (
                    <span key={mIdx} className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider border-2 border-[#111] bg-white">
                      {method}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
