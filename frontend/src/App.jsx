import { useState, useEffect, useRef } from 'react'
import { MessageSquare, AlertCircle, CheckCircle, Bug, HelpCircle, Lightbulb } from 'lucide-react'

function App() {
    const [issues, setIssues] = useState([])
    const [selectedIssue, setSelectedIssue] = useState(null)
    const [messages, setMessages] = useState([])
    const selectedIssueRef = useRef(null)

    useEffect(() => {
        selectedIssueRef.current = selectedIssue
    }, [selectedIssue])

    useEffect(() => {
        fetchIssues()

        // SSE Connection
        const eventSource = new EventSource('http://localhost:8000/events')

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data)
            console.log("New event:", data)
            if (data.type === "new_message") {
                fetchIssues() // Always refresh issues list
                // If the new message belongs to the currently selected issue, refresh messages
                if (selectedIssueIdRef.current && selectedIssueIdRef.current === data.issue_id) {
                    fetchMessages(data.issue_id)
                }
            } else if (data.type === "issue_resolved") {
                fetchIssues()
                if (selectedIssueIdRef.current && selectedIssueIdRef.current === data.issue_id) {
                    // Update local state if selected
                    setSelectedIssue(prev => prev ? ({ ...prev, status: 'resolved' }) : null)
                }
            }
        }

        eventSource.onerror = (err) => {
            console.error("EventSource failed:", err)
            eventSource.close()
        }

        return () => {
            eventSource.close()
        }
    }, [])

    useEffect(() => {
        if (selectedIssue) {
            fetchMessages(selectedIssue.id)
        }
    }, [selectedIssue])

    const fetchIssues = async () => {
        try {
            const res = await fetch('http://localhost:8000/issues')
            const data = await res.json()
            setIssues(data)
        } catch (error) {
            console.error("Error fetching issues:", error)
        }
    }

    const fetchMessages = async (issueId) => {
        try {
            const res = await fetch(`http://localhost:8000/issues/${issueId}/messages`)
            const data = await res.json()
            setMessages(data)
        } catch (error) {
            console.error("Error fetching messages:", error)
        }
    }

    const resolveIssue = async (issueId) => {
        try {
            const res = await fetch(`http://localhost:8000/issues/${issueId}/resolve`, { method: 'PUT' })
            if (res.ok) {
                fetchIssues()
                // Optimistic update
                setSelectedIssue(prev => ({ ...prev, status: 'resolved' }))
            }
        } catch (error) {
            console.error("Error resolving issue:", error)
        }
    }

    const getIcon = (type) => {
        switch (type) {
            case 'bug_report': return <Bug className="w-5 h-5 text-red-500" />
            case 'support_question': return <HelpCircle className="w-5 h-5 text-blue-500" />
            case 'feature_request': return <Lightbulb className="w-5 h-5 text-yellow-500" />
            default: return <MessageSquare className="w-5 h-5 text-gray-500" />
        }
    }

    return (
        <div className="flex h-screen bg-gray-100">
            {/* Sidebar */}
            <div className="w-1/3 bg-white border-r border-gray-200 overflow-y-auto">
                <div className="p-4 border-b border-gray-200">
                    <h1 className="text-xl font-bold text-gray-800">FDE Dashboard</h1>
                    <div className="text-xs text-green-600 flex items-center gap-1 mt-1">
                        <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                        Live Updates Active
                    </div>
                </div>
                <ul>
                    {issues.map(issue => (
                        <li
                            key={issue.id}
                            className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 ${selectedIssue?.id === issue.id ? 'bg-blue-50' : ''}`}
                            onClick={() => setSelectedIssue(issue)}
                        >
                            <div className="flex items-center justify-between mb-1">
                                <span className="font-semibold text-gray-700 truncate">{issue.title}</span>
                                <span className="text-xs text-gray-500">{new Date(issue.updated_at).toLocaleTimeString()}</span>
                            </div>
                            <div className="text-sm text-gray-500 truncate">{issue.summary || "No summary"}</div>
                        </li>
                    ))}
                </ul>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col">
                {selectedIssue ? (
                    <>
                        <div className="p-6 bg-white border-b border-gray-200 shadow-sm flex justify-between items-start">
                            <div>
                                <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
                                    {selectedIssue.title}
                                    {selectedIssue.status === 'resolved' && (
                                        <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full border border-green-200">Resolved</span>
                                    )}
                                </h2>
                                <p className="text-gray-500 mt-1">{selectedIssue.summary}</p>
                            </div>
                            {selectedIssue.status !== 'resolved' && (
                                <button
                                    onClick={() => resolveIssue(selectedIssue.id)}
                                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium flex items-center gap-2"
                                >
                                    <CheckCircle className="w-4 h-4" />
                                    Resolve Issue
                                </button>
                            )}
                        </div>
                        <div className="flex-1 p-6 overflow-y-auto space-y-4">
                            {messages.map(msg => (
                                <div key={msg.id} className="bg-white p-4 rounded-lg shadow-sm border border-gray-100">
                                    <div className="flex items-center gap-2 mb-2">
                                        {getIcon(msg.classification)}
                                        <span className="font-medium text-gray-700">User {msg.user_id}</span>
                                        <span className="text-xs text-gray-400">{new Date(msg.timestamp).toLocaleString()}</span>
                                    </div>
                                    <p className="text-gray-800">{msg.text}</p>
                                    <div className="mt-2 flex items-center gap-2">
                                        <span className="text-xs px-2 py-1 bg-gray-100 rounded-full text-gray-600">{msg.classification}</span>
                                        <span className="text-xs text-gray-400">Confidence: {(msg.confidence * 100).toFixed(0)}%</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex items-center justify-center text-gray-400">
                        Select an issue to view details
                    </div>
                )}
            </div>
        </div>
    )
}

export default App
