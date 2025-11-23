import { useState, useEffect, useRef, Fragment } from 'react'
import {
    Activity, CheckCircle,
    TrendingUp, Clock, BarChart3, Home, Inbox, Archive, Settings,
    Ticket, Users, ChevronDown
} from 'lucide-react'


function App() {
    const [issues, setIssues] = useState([])
    const [selectedIssue, setSelectedIssue] = useState(null)
    const [messages, setMessages] = useState([])
    const [isConnected, setIsConnected] = useState(false)
    const [activeView, setActiveView] = useState('all')
    const [expandedTicket, setExpandedTicket] = useState(null)
    const [expandedUser, setExpandedUser] = useState(null)
    const [ticketMessages, setTicketMessages] = useState({})
    const selectedIssueRef = useRef(null)
    const expandedTicketRef = useRef(null)

    useEffect(() => {
        selectedIssueRef.current = selectedIssue
    }, [selectedIssue])

    useEffect(() => {
        expandedTicketRef.current = expandedTicket
    }, [expandedTicket])

    useEffect(() => {
        fetchIssues()

        const eventSource = new EventSource('http://localhost:8000/events')

        eventSource.onopen = () => {
            setIsConnected(true)
        }

        eventSource.onmessage = async (event) => {
            const data = JSON.parse(event.data)
            if (data.type === "new_message") {
                fetchIssues()
                if (selectedIssueRef.current && selectedIssueRef.current.id === data.issue_id) {
                    fetchMessages(data.issue_id)
                }
                // Also update ticketMessages if this issue is currently expanded
                if (expandedTicketRef.current === data.issue_id) {
                    try {
                        const res = await fetch(`http://localhost:8000/issues/${data.issue_id}/messages`)
                        const messages = await res.json()
                        setTicketMessages(prev => ({ ...prev, [data.issue_id]: messages }))
                    } catch (error) {
                        console.error("Error fetching updated messages:", error)
                    }
                }
            } else if (data.type === "issue_resolved") {
                fetchIssues()
                if (selectedIssueRef.current && selectedIssueRef.current.id === data.issue_id) {
                    setSelectedIssue(prev => prev ? ({ ...prev, status: 'resolved' }) : null)
                }
            }
        }

        eventSource.onerror = (err) => {
            console.error("EventSource failed:", err)
            setIsConnected(false)
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
                setSelectedIssue(prev => ({ ...prev, status: 'resolved' }))
            }
        } catch (error) {
            console.error("Error resolving issue:", error)
        }
    }

    const handleTicketClick = async (issue) => {
        if (expandedTicket === issue.id) {
            setExpandedTicket(null)
        } else {
            setExpandedTicket(issue.id)
            // Fetch messages for this ticket if not already loaded
            if (!ticketMessages[issue.id]) {
                try {
                    const res = await fetch(`http://localhost:8000/issues/${issue.id}/messages`)
                    const data = await res.json()
                    setTicketMessages(prev => ({ ...prev, [issue.id]: data }))
                } catch (error) {
                    console.error("Error fetching ticket messages:", error)
                }
            }
        }
    }



    const getBadgeClass = (type) => {
        switch (type) {
            case 'bug_report': return 'badge-error'
            case 'support_question': return 'badge-info'
            case 'feature_request': return 'badge-warning'
            default: return 'badge-info'
        }
    }

    const getAvatarColor = (userId) => {
        const colors = [
            'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
            'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
            'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
        ]
        const hash = userId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
        return colors[hash % colors.length]
    }

    const activeIssues = issues.filter(i => i.status !== 'resolved')
    const resolvedIssues = issues.filter(i => i.status === 'resolved')
    const totalMessages = issues.reduce((sum, issue) => sum + (issue.message_count || 0), 0)

    // Get filtered issues based on active view
    const filteredIssues = activeView === 'active' ? activeIssues :
        activeView === 'resolved' ? resolvedIssues : issues

    return (
        <div className="flex h-screen bg-[var(--bg-secondary)]">
            {/* Sidebar */}
            <div className="sidebar animate-slide-in-left">
                <div className="sidebar-header">
                    <div className="flex items-center gap-3">
                        <img
                            src="/nixo-logo.png"
                            alt="Nixo Logo"
                            className="w-10 h-10"
                            onError={(e) => {
                                // Fallback to gradient if logo fails to load
                                e.target.style.display = 'none';
                                e.target.nextElementSibling.style.display = 'flex';
                            }}
                        />
                        <div
                            className="w-10 h-10 rounded-lg bg-gradient-to-br from-pink-500 to-purple-600 items-center justify-center"
                            style={{ display: 'none' }}
                        >
                            <TrendingUp className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h1 className="font-bold text-lg">Nixo</h1>
                            <div className="flex items-center gap-2.5 mt-0.5">
                                <span className={`status-dot ${isConnected ? 'online' : 'offline'}`}></span>
                                <span className="text-xs text-muted">{isConnected ? 'Live' : 'Offline'}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="sidebar-nav">
                    <div className="mb-4">
                        <div className="text-xs font-semibold text-muted uppercase tracking-wider mb-2 px-3">
                            Navigation
                        </div>
                        <div
                            className={`sidebar-item ${activeView === 'all' ? 'active' : ''}`}
                            onClick={() => setActiveView('all')}
                        >
                            <Home className="w-4 h-4" />
                            <span>All Issues</span>
                            <span className="ml-auto text-xs bg-[var(--bg-tertiary)] px-2 py-0.5 rounded-full">
                                {issues.length}
                            </span>
                        </div>
                        <div
                            className={`sidebar-item ${activeView === 'active' ? 'active' : ''}`}
                            onClick={() => setActiveView('active')}
                        >
                            <Inbox className="w-4 h-4" />
                            <span>Active</span>
                            <span className="ml-auto text-xs bg-[var(--status-warning-bg)] text-[var(--status-warning)] px-2 py-0.5 rounded-full font-semibold">
                                {activeIssues.length}
                            </span>
                        </div>
                        <div
                            className={`sidebar-item ${activeView === 'resolved' ? 'active' : ''}`}
                            onClick={() => setActiveView('resolved')}
                        >
                            <Archive className="w-4 h-4" />
                            <span>Resolved</span>
                            <span className="ml-auto text-xs text-muted">
                                {resolvedIssues.length}
                            </span>
                        </div>
                        <div
                            className={`sidebar-item ${activeView === 'tickets' ? 'active' : ''}`}
                            onClick={() => setActiveView('tickets')}
                        >
                            <Ticket className="w-4 h-4" />
                            <span>Tickets</span>
                            <span className="ml-auto text-xs text-muted">
                                {issues.length}
                            </span>
                        </div>
                        <div
                            className={`sidebar-item ${activeView === 'users' ? 'active' : ''}`}
                            onClick={() => setActiveView('users')}
                        >
                            <Users className="w-4 h-4" />
                            <span>Users</span>
                        </div>
                    </div>

                    <div className="divider"></div>

                    <div>
                        <div className="text-xs font-semibold text-muted uppercase tracking-wider mb-2 px-3">
                            Settings
                        </div>
                        <div className="sidebar-item">
                            <Settings className="w-4 h-4" />
                            <span>Preferences</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="main-content">
                {/* Header */}
                <div className="page-header">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="text-xl font-bold mb-1">
                                {activeView === 'all' ? 'All Issues' :
                                    activeView === 'active' ? 'Active Issues' :
                                        activeView === 'resolved' ? 'Resolved Issues' :
                                            activeView === 'tickets' ? 'Tickets' : 'Users'}
                            </h2>
                            <p className="text-sm text-muted">
                                {activeView === 'tickets' ? 'Manage and track all customer tickets' :
                                    activeView === 'users' ? 'View user activity and statistics' :
                                        'Real-time customer issue monitoring and tracking'}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Metrics */}
                <div className="p-6">
                    {/* Metrics - Only show on Home/All Issues */}
                    {activeView === 'all' && (
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 animate-fade-in">
                            <div className="metric-card-modern">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="w-10 h-10 rounded-lg bg-[var(--status-warning-bg)] flex items-center justify-center">
                                        <Activity className="w-5 h-5 text-[var(--status-warning)]" />
                                    </div>
                                </div>
                                <div className="text-2xl font-bold mb-1">{activeIssues.length}</div>
                                <div className="text-sm text-muted">Active Issues</div>
                            </div>

                            <div className="metric-card-modern">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="w-10 h-10 rounded-lg bg-[var(--status-success-bg)] flex items-center justify-center">
                                        <CheckCircle className="w-5 h-5 text-[var(--status-success)]" />
                                    </div>
                                </div>
                                <div className="text-2xl font-bold mb-1">{resolvedIssues.length}</div>
                                <div className="text-sm text-muted">Resolved Today</div>
                            </div>

                            <div className="metric-card-modern">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="w-10 h-10 rounded-lg bg-[var(--status-info-bg)] flex items-center justify-center">
                                        <BarChart3 className="w-5 h-5 text-[var(--status-info)]" />
                                    </div>
                                </div>
                                <div className="text-2xl font-bold mb-1">{totalMessages}</div>
                                <div className="text-sm text-muted">Total Messages</div>
                            </div>

                            <div className="metric-card-modern">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="w-10 h-10 rounded-lg bg-[var(--brand-primary-light)] flex items-center justify-center">
                                        <Clock className="w-5 h-5 text-[var(--brand-primary)]" />
                                    </div>
                                </div>
                                <div className="text-2xl font-bold mb-1">~8s</div>
                                <div className="text-sm text-muted">Avg Response</div>
                            </div>
                        </div>
                    )}

                    {/* Content based on active view */}
                    {activeView === 'tickets' || activeView === 'active' || activeView === 'resolved' ? (
                        /* Table View for Tickets, Active, and Resolved */
                        <div className="card-modern">
                            {(activeView === 'tickets' ? issues : activeView === 'active' ? activeIssues : resolvedIssues).length === 0 ? (
                                <div className="p-12">
                                    <div className="empty-state">
                                        <Ticket className="empty-state-icon mx-auto" />
                                        <h3 className="text-lg font-semibold mb-2">No items found</h3>
                                        <p className="text-sm">There are no items to display at the moment.</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full">
                                        <thead className="bg-[var(--bg-secondary)] border-b border-[var(--border-light)]">
                                            <tr>
                                                <th className="text-left p-4 text-xs font-semibold text-muted uppercase">ID</th>
                                                <th className="text-left p-4 text-xs font-semibold text-muted uppercase">Title</th>
                                                <th className="text-left p-4 text-xs font-semibold text-muted uppercase">Type</th>
                                                <th className="text-left p-4 text-xs font-semibold text-muted uppercase">Status</th>
                                                <th className="text-left p-4 text-xs font-semibold text-muted uppercase">Updated</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {(activeView === 'tickets' ? issues : activeView === 'active' ? activeIssues : resolvedIssues).map((issue, index) => (
                                                <Fragment key={issue.id}>
                                                    <tr
                                                        className="border-b border-[var(--border-light)] hover:bg-[var(--bg-hover)] cursor-pointer transition-colors"
                                                        onClick={() => handleTicketClick(issue)}
                                                    >
                                                        <td className="p-4">
                                                            <div className="flex items-center gap-2">
                                                                <ChevronDown
                                                                    className={`w-4 h-4 transition-transform ${expandedTicket === issue.id ? 'rotate-180' : ''}`}
                                                                />
                                                                <span className="text-sm text-muted">#{String(issue.id).slice(0, 8)}</span>
                                                            </div>
                                                        </td>
                                                        <td className="p-4">
                                                            <div className="font-medium text-sm">{issue.title}</div>
                                                            <div className="text-xs text-muted truncate max-w-md">{issue.summary}</div>
                                                        </td>
                                                        <td className="p-4">
                                                            <span className={`badge-modern ${getBadgeClass(issue.classification)}`}>
                                                                {issue.classification?.replace('_', ' ')}
                                                            </span>
                                                        </td>
                                                        <td className="p-4">
                                                            {issue.status === 'resolved' ? (
                                                                <span className="badge-modern badge-success">
                                                                    <CheckCircle className="w-3 h-3" />
                                                                    Resolved
                                                                </span>
                                                            ) : (
                                                                <span className="badge-modern badge-warning">Active</span>
                                                            )}
                                                        </td>
                                                        <td className="p-4 text-sm text-muted">
                                                            {new Date(issue.updated_at).toLocaleDateString([], {
                                                                month: 'short',
                                                                day: 'numeric',
                                                                hour: '2-digit',
                                                                minute: '2-digit'
                                                            })}
                                                        </td>
                                                    </tr>
                                                    {expandedTicket === issue.id && (
                                                        <tr className="bg-[var(--bg-secondary)]">
                                                            <td colSpan="5" className="p-6">
                                                                <div className="space-y-3">
                                                                    <h4 className="text-sm font-semibold mb-3">Messages ({ticketMessages[issue.id]?.length || 0})</h4>
                                                                    {ticketMessages[issue.id] && ticketMessages[issue.id].length > 0 ? (
                                                                        ticketMessages[issue.id].map((msg) => (
                                                                            <div key={msg.id} className="message-bubble">
                                                                                <div className="flex items-start gap-3 mb-2">
                                                                                    <div
                                                                                        className="avatar avatar-sm"
                                                                                        style={{ background: getAvatarColor(msg.user_id) }}
                                                                                    >
                                                                                        <span className="text-white">
                                                                                            {msg.user_id[0].toUpperCase()}
                                                                                        </span>
                                                                                    </div>
                                                                                    <div className="flex-1 min-w-0">
                                                                                        <div className="flex items-center gap-2 mb-1">
                                                                                            <span className="font-semibold text-sm">User {msg.user_id}</span>
                                                                                            <span className="text-xs text-subtle">
                                                                                                {new Date(msg.timestamp).toLocaleString([], {
                                                                                                    hour: '2-digit',
                                                                                                    minute: '2-digit'
                                                                                                })}
                                                                                            </span>
                                                                                        </div>
                                                                                        <p className="text-sm mb-2">{msg.text}</p>
                                                                                        <div className="flex items-center gap-2">
                                                                                            <span className={`badge-modern ${getBadgeClass(msg.classification)}`}>
                                                                                                {msg.classification?.replace('_', ' ')}
                                                                                            </span>
                                                                                            <span className="text-xs text-subtle">
                                                                                                {(msg.confidence * 100).toFixed(0)}% confidence
                                                                                            </span>
                                                                                        </div>
                                                                                    </div>
                                                                                </div>
                                                                            </div>
                                                                        ))
                                                                    ) : (
                                                                        <p className="text-sm text-muted">No messages yet</p>
                                                                    )}
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    )}
                                                </Fragment>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    ) : activeView === 'users' ? (
                        /* Users View - User Cards */
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {(() => {
                                // Extract unique users from issues and all cached messages
                                const userMap = new Map();
                                const issueUserMap = new Map(); // Track which issues each user is involved in

                                // First, collect users from issues themselves
                                issues.forEach(issue => {
                                    if (issue.user_id) {
                                        if (!userMap.has(issue.user_id)) {
                                            userMap.set(issue.user_id, {
                                                id: issue.user_id,
                                                messageCount: 0,
                                                issueCount: 0,
                                                lastActive: issue.updated_at
                                            });
                                            issueUserMap.set(issue.user_id, new Set());
                                        }
                                        issueUserMap.get(issue.user_id).add(issue.id);
                                        const user = userMap.get(issue.user_id);
                                        user.issueCount++;
                                        if (new Date(issue.updated_at) > new Date(user.lastActive)) {
                                            user.lastActive = issue.updated_at;
                                        }
                                    }
                                });

                                // Then, collect users from all cached ticket messages
                                Object.values(ticketMessages).forEach(messageList => {
                                    if (messageList) {
                                        messageList.forEach(msg => {
                                            const userId = msg.user_id;
                                            if (!userMap.has(userId)) {
                                                userMap.set(userId, {
                                                    id: userId,
                                                    messageCount: 0,
                                                    issueCount: 0,
                                                    lastActive: msg.timestamp
                                                });
                                                issueUserMap.set(userId, new Set());
                                            }
                                            const user = userMap.get(userId);
                                            user.messageCount++;
                                            if (new Date(msg.timestamp) > new Date(user.lastActive)) {
                                                user.lastActive = msg.timestamp;
                                            }
                                        });
                                    }
                                });

                                // If no users found, show empty state
                                if (userMap.size === 0) {
                                    return (
                                        <div className="col-span-full">
                                            <div className="card-modern p-12">
                                                <div className="empty-state">
                                                    <Users className="empty-state-icon mx-auto" />
                                                    <h3 className="text-lg font-semibold mb-2">No users found</h3>
                                                    <p className="text-sm">Users will appear here once issues are created</p>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                }

                                return Array.from(userMap.values()).map(user => (
                                    <div key={user.id} className="card-modern p-6 hover-lift">
                                        <div className="flex items-start gap-4">
                                            <div
                                                className="avatar avatar-lg"
                                                style={{ background: getAvatarColor(user.id) }}
                                            >
                                                <span className="text-white text-lg">
                                                    {user.id[0].toUpperCase()}
                                                </span>
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <h3 className="font-bold text-base mb-1">User {user.id}</h3>
                                                <p className="text-xs text-muted mb-3">
                                                    Last active {new Date(user.lastActive).toLocaleDateString([], {
                                                        month: 'short',
                                                        day: 'numeric',
                                                        hour: '2-digit',
                                                        minute: '2-digit'
                                                    })}
                                                </p>
                                                <div className="grid grid-cols-2 gap-3">
                                                    <div className="bg-[var(--bg-secondary)] rounded-lg p-3">
                                                        <div className="text-xs text-muted mb-1">Messages</div>
                                                        <div className="text-lg font-bold">{user.messageCount}</div>
                                                    </div>
                                                    <div className="bg-[var(--bg-secondary)] rounded-lg p-3">
                                                        <div className="text-xs text-muted mb-1">Issues</div>
                                                        <div className="text-lg font-bold">{user.issueCount}</div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ));
                            })()}
                        </div>
                    ) : (
                        /* Issues List - Default View (Only for 'all') with expandable dropdowns */
                        <div className="card-modern">
                            {filteredIssues.length === 0 ? (
                                <div className="p-12">
                                    <div className="empty-state">
                                        <CheckCircle className="empty-state-icon mx-auto" />
                                        <h3 className="text-lg font-semibold mb-2">No issues found</h3>
                                        <p className="text-sm">All caught up! No {activeView} issues at the moment.</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full">
                                        <thead className="bg-[var(--bg-secondary)] border-b border-[var(--border-light)]">
                                            <tr>
                                                <th className="text-left p-4 text-xs font-semibold text-muted uppercase">ID</th>
                                                <th className="text-left p-4 text-xs font-semibold text-muted uppercase">Title</th>
                                                <th className="text-left p-4 text-xs font-semibold text-muted uppercase">Type</th>
                                                <th className="text-left p-4 text-xs font-semibold text-muted uppercase">Status</th>
                                                <th className="text-left p-4 text-xs font-semibold text-muted uppercase">Updated</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {filteredIssues.map((issue, index) => (
                                                <Fragment key={issue.id}>
                                                    <tr
                                                        className="border-b border-[var(--border-light)] hover:bg-[var(--bg-hover)] cursor-pointer transition-colors"
                                                        onClick={() => handleTicketClick(issue)}
                                                    >
                                                        <td className="p-4">
                                                            <div className="flex items-center gap-2">
                                                                <ChevronDown
                                                                    className={`w-4 h-4 transition-transform ${expandedTicket === issue.id ? 'rotate-180' : ''}`}
                                                                />
                                                                <span className="text-sm text-muted">#{String(issue.id).slice(0, 8)}</span>
                                                            </div>
                                                        </td>
                                                        <td className="p-4">
                                                            <div className="font-medium text-sm">{issue.title}</div>
                                                            <div className="text-xs text-muted truncate max-w-md">{issue.summary}</div>
                                                        </td>
                                                        <td className="p-4">
                                                            <span className={`badge-modern ${getBadgeClass(issue.classification)}`}>
                                                                {issue.classification?.replace('_', ' ')}
                                                            </span>
                                                        </td>
                                                        <td className="p-4">
                                                            {issue.status === 'resolved' ? (
                                                                <span className="badge-modern badge-success">
                                                                    <CheckCircle className="w-3 h-3" />
                                                                    Resolved
                                                                </span>
                                                            ) : (
                                                                <span className="badge-modern badge-warning">Active</span>
                                                            )}
                                                        </td>
                                                        <td className="p-4 text-sm text-muted">
                                                            {new Date(issue.updated_at).toLocaleDateString([], {
                                                                month: 'short',
                                                                day: 'numeric',
                                                                hour: '2-digit',
                                                                minute: '2-digit'
                                                            })}
                                                        </td>
                                                    </tr>
                                                    {expandedTicket === issue.id && (
                                                        <tr className="bg-[var(--bg-secondary)]">
                                                            <td colSpan="5" className="p-6">
                                                                <div className="space-y-4">
                                                                    {/* Issue Details Section */}
                                                                    <div className="bg-[var(--bg-primary)] rounded-lg p-4 mb-4">
                                                                        <h4 className="text-sm font-semibold mb-3">Issue Details</h4>
                                                                        <div className="grid grid-cols-2 gap-3 text-sm">
                                                                            <div>
                                                                                <span className="text-muted">Created:</span>
                                                                                <span className="ml-2">
                                                                                    {new Date(issue.created_at || issue.updated_at).toLocaleDateString([], {
                                                                                        month: 'short',
                                                                                        day: 'numeric',
                                                                                        hour: '2-digit',
                                                                                        minute: '2-digit'
                                                                                    })}
                                                                                </span>
                                                                            </div>
                                                                            <div>
                                                                                <span className="text-muted">Messages:</span>
                                                                                <span className="ml-2">{ticketMessages[issue.id]?.length || 0}</span>
                                                                            </div>
                                                                        </div>
                                                                        {issue.status !== 'resolved' && (
                                                                            <button
                                                                                onClick={(e) => {
                                                                                    e.stopPropagation();
                                                                                    resolveIssue(issue.id);
                                                                                }}
                                                                                className="btn-modern btn-success w-full mt-3"
                                                                            >
                                                                                <CheckCircle className="w-4 h-4" />
                                                                                Mark as Resolved
                                                                            </button>
                                                                        )}
                                                                    </div>

                                                                    {/* Messages Section */}
                                                                    <h4 className="text-sm font-semibold mb-3">Messages ({ticketMessages[issue.id]?.length || 0})</h4>
                                                                    {ticketMessages[issue.id] && ticketMessages[issue.id].length > 0 ? (
                                                                        ticketMessages[issue.id].map((msg) => (
                                                                            <div key={msg.id} className="message-bubble">
                                                                                <div className="flex items-start gap-3 mb-2">
                                                                                    <div
                                                                                        className="avatar avatar-sm"
                                                                                        style={{ background: getAvatarColor(msg.user_id) }}
                                                                                    >
                                                                                        <span className="text-white">
                                                                                            {msg.user_id[0].toUpperCase()}
                                                                                        </span>
                                                                                    </div>
                                                                                    <div className="flex-1 min-w-0">
                                                                                        <div className="flex items-center gap-2 mb-1">
                                                                                            <span className="font-semibold text-sm">User {msg.user_id}</span>
                                                                                            <span className="text-xs text-subtle">
                                                                                                {new Date(msg.timestamp).toLocaleString([], {
                                                                                                    hour: '2-digit',
                                                                                                    minute: '2-digit'
                                                                                                })}
                                                                                            </span>
                                                                                        </div>
                                                                                        <p className="text-sm mb-2">{msg.text}</p>
                                                                                        <div className="flex items-center gap-2">
                                                                                            <span className={`badge-modern ${getBadgeClass(msg.classification)}`}>
                                                                                                {msg.classification?.replace('_', ' ')}
                                                                                            </span>
                                                                                            <span className="text-xs text-subtle">
                                                                                                {(msg.confidence * 100).toFixed(0)}% confidence
                                                                                            </span>
                                                                                        </div>
                                                                                    </div>
                                                                                </div>
                                                                            </div>
                                                                        ))
                                                                    ) : (
                                                                        <p className="text-sm text-muted">No messages yet</p>
                                                                    )}
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    )}
                                                </Fragment>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

export default App
