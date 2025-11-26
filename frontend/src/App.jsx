import { useState, useEffect, useRef, useCallback } from 'react'
import {
    Activity, CheckCircle,
    TrendingUp, Clock, BarChart3, Home, Inbox, Archive, Settings,
    Ticket, Users, ChevronDown
} from 'lucide-react'


function App() {
    const [issues, setIssues] = useState([])
    const [isConnected, setIsConnected] = useState(false)
    const [activeView, setActiveView] = useState('all')
    const [expandedTicket, setExpandedTicket] = useState(null)
    const [ticketMessages, setTicketMessages] = useState({})
    const [analytics, setAnalytics] = useState({ totalMessages: 0, uniqueUsers: 0 })
    const [searchTerm, setSearchTerm] = useState('')
    const [classificationFilter, setClassificationFilter] = useState('all')
    const expandedTicketRef = useRef(null)
    const prefetchedIssuesRef = useRef(new Set())

    const fetchIssueMessages = useCallback(async (issueId) => {
        try {
            const res = await fetch(`http://localhost:8000/issues/${issueId}/messages`)
            if (!res.ok) {
                return []
            }
            const data = await res.json()
            setTicketMessages(prev => ({ ...prev, [issueId]: data }))
            prefetchedIssuesRef.current.add(issueId)
            return data
        } catch (error) {
            console.error(`Error fetching messages for issue ${issueId}:`, error)
            return []
        }
    }, [])

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
                await fetchIssueMessages(data.issue_id)
            } else if (data.type === "issue_resolved") {
                fetchIssues()
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
    }, [fetchIssueMessages])

    const fetchIssues = async () => {
        try {
            const res = await fetch('http://localhost:8000/issues')
            const data = await res.json()
            setIssues(data)
        } catch (error) {
            console.error("Error fetching issues:", error)
        }
    }

    const resolveIssue = async (issueId) => {
        try {
            const res = await fetch(`http://localhost:8000/issues/${issueId}/resolve`, { method: 'PUT' })
            if (res.ok) {
                fetchIssues()
            }
        } catch (error) {
            console.error("Error resolving issue:", error)
        }
    }

    useEffect(() => {
        if (!issues.length) {
            prefetchedIssuesRef.current.clear()
            setTicketMessages({})
            return
        }

        const missingIssues = issues.filter(issue => !prefetchedIssuesRef.current.has(issue.id))
        if (missingIssues.length === 0) {
            return
        }

        let cancelled = false

        const preload = async () => {
            for (const issue of missingIssues) {
                if (cancelled) {
                    return
                }
                await fetchIssueMessages(issue.id)
            }
        }

        preload()

        return () => {
            cancelled = true
        }
    }, [issues, fetchIssueMessages])

    useEffect(() => {
        const userSet = new Set()
        let total = 0
        Object.values(ticketMessages).forEach(messageList => {
            if (!Array.isArray(messageList)) {
                return
            }
            total += messageList.length
            messageList.forEach(msg => {
                if (msg?.user_id) {
                    userSet.add(msg.user_id)
                }
            })
        })
        setAnalytics({
            totalMessages: total,
            uniqueUsers: userSet.size
        })
    }, [ticketMessages])

    const handleTicketClick = async (issue) => {
        if (expandedTicket === issue.id) {
            setExpandedTicket(null)
        } else {
            setExpandedTicket(issue.id)
            // Fetch messages for this ticket if not already loaded
            if (!ticketMessages[issue.id]) {
                await fetchIssueMessages(issue.id)
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

    const formatDateTime = (value) => {
        if (!value) {
            return '--'
        }
        return new Date(value).toLocaleDateString([], {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        })
    }

    const getIssuePrimaryUser = (issue) => {
        const messagesForIssue = ticketMessages[issue.id]
        if (messagesForIssue && messagesForIssue.length > 0) {
            return messagesForIssue[0]?.user_id || issue.user_id
        }
        return issue.user_id
    }

    const activeIssues = issues.filter(i => i.status !== 'resolved')
    const resolvedIssues = issues.filter(i => i.status === 'resolved')

    const viewMeta = {
        all: {
            title: 'All Issues',
            description: 'Real-time customer issue monitoring and tracking.',
            empty: 'All caught up! There are no issues requiring attention at the moment.'
        },
        active: {
            title: 'Active Issues',
            description: 'Focus on the conversations that still need a human touch.',
            empty: 'No open issues. Enjoy the calm while it lasts.'
        },
        resolved: {
            title: 'Resolved Issues',
            description: 'Celebrate every ticket that finds a happy ending.',
            empty: 'Nothing in the archive just yet.'
        },
        tickets: {
            title: 'Tickets',
            description: 'Manage and track every customer conversation in one place.',
            empty: 'No tickets have been created yet.'
        },
        users: {
            title: 'Users',
            description: 'View user activity and statistics.',
            empty: 'Users will appear once issues are created and conversations start.'
        }
    }

    const classificationFilters = [
        { value: 'all', label: 'All', subtitle: 'Every classification' },
        { value: 'bug_report', label: 'Bugs', subtitle: 'Regression & crashes' },
        { value: 'support_question', label: 'Support', subtitle: 'How-to & help' },
        { value: 'feature_request', label: 'Features', subtitle: 'Ideas & feedback' }
    ]

    const classificationSummary = issues.reduce((acc, issue) => {
        const key = issue.classification
        if (!key) return acc
        acc[key] = (acc[key] || 0) + 1
        return acc
    }, {})

    const viewTabs = [
        { id: 'all', label: 'All', icon: Home, count: issues.length },
        { id: 'active', label: 'Active', icon: Inbox, count: activeIssues.length },
        { id: 'resolved', label: 'Resolved', icon: Archive, count: resolvedIssues.length },
        { id: 'tickets', label: 'Tickets', icon: Ticket, count: issues.length },
        { id: 'users', label: 'Users', icon: Users, count: analytics.uniqueUsers }
    ]

    const issuesForView = activeView === 'tickets'
        ? issues
        : activeView === 'active'
            ? activeIssues
            : activeView === 'resolved'
                ? resolvedIssues
                : issues

    const filteredIssues = issuesForView
        .filter(issue => classificationFilter === 'all' ? true : issue.classification === classificationFilter)
        .filter(issue => {
            if (!searchTerm.trim()) return true
            const term = searchTerm.trim().toLowerCase()
            const comparableValues = [
                issue.title,
                issue.summary,
                issue.classification,
                issue.id ? `#${issue.id}` : ''
            ]
            return comparableValues
                .filter(Boolean)
                .some(value => value.toString().toLowerCase().includes(term))
        })

    const heroCopy = viewMeta[activeView] || viewMeta.all
    const showIssueFilters = activeView !== 'users'
    const hasActiveFilters = showIssueFilters && (classificationFilter !== 'all' || searchTerm.trim().length > 0)

    const handleViewChange = (view) => {
        setActiveView(view)
        setExpandedTicket(null)
    }

    const renderIssueCards = (collection) => {
        return (
            <div className="card-modern elevated-surface issue-stack">
                {collection.length === 0 ? (
                    <div className="empty-state modern-empty">
                        <div className="emoji-badge">{hasActiveFilters ? '🔍' : '✨'}</div>
                        <h3 className="text-xl font-bold mb-2 text-[var(--text-primary)]">
                            {hasActiveFilters ? 'No matches for your filters' : 'No records just yet'}
                        </h3>
                        <p className="text-[var(--text-secondary)] max-w-md mx-auto">
                            {hasActiveFilters
                                ? 'Try clearing the filters or searching with a different keyword.'
                                : heroCopy.empty}
                        </p>
                    </div>
                ) : (
                    <div className="issue-collection">
                        {collection.map((issue) => {
                            const messageCount = ticketMessages[issue.id]?.length ?? issue.message_count ?? 0
                            return (
                                <div
                                    key={issue.id}
                                    className={`issue-row ${expandedTicket === issue.id ? 'expanded' : ''}`}
                                    onClick={() => handleTicketClick(issue)}
                                >
                                    <div className="issue-row-header">
                                        <div className="issue-id-chip">#{String(issue.id).slice(0, 8)}</div>
                                        <div className="issue-title-block">
                                            <h3>{issue.title}</h3>
                                            <p className="issue-summary">{issue.summary}</p>
                                        </div>
                                        <div className="issue-chip-stack">
                                            <span className={`badge-modern ${getBadgeClass(issue.classification)}`}>
                                                {issue.classification?.replace('_', ' ')}
                                            </span>
                                            {issue.status === 'resolved' ? (
                                                <span className="badge-modern badge-success">
                                                    <CheckCircle className="w-3 h-3" />
                                                    Resolved
                                                </span>
                                            ) : (
                                                <span className="badge-modern badge-warning">Active</span>
                                            )}
                                        </div>
                                        <ChevronDown
                                            className={`w-4 h-4 text-[var(--text-tertiary)] transition-transform ${expandedTicket === issue.id ? 'rotate-180' : ''}`}
                                        />
                                    </div>
                                    <div className="issue-row-meta">
                                        <div className="meta-block">
                                            <span className="meta-label">Updated</span>
                                            <span className="meta-value">{formatDateTime(issue.updated_at)}</span>
                                        </div>
                                        <div className="meta-block">
                                            <span className="meta-label">Messages</span>
                                            <span className="meta-value">{messageCount}</span>
                                        </div>
                                        <div className="meta-block">
                                            <span className="meta-label">User</span>
                                    <span className="meta-value">{getIssuePrimaryUser(issue) || 'Unknown'}</span>
                                        </div>
                                    </div>
                                    {expandedTicket === issue.id && (
                                        <div
                                            className="issue-row-details"
                                            onClick={(event) => event.stopPropagation()}
                                        >
                                            <div className="issue-detail-panel">
                                                <div className="issue-detail-grid">
                                                    <div>
                                                        <span className="meta-label">Created</span>
                                                        <span className="meta-value">{formatDateTime(issue.created_at || issue.updated_at)}</span>
                                                    </div>
                                                    <div>
                                                        <span className="meta-label">Messages</span>
                                                        <span className="meta-value">{messageCount}</span>
                                                    </div>
                                                </div>
                                                {issue.status !== 'resolved' && (
                                                    <button
                                                        onClick={(event) => {
                                                            event.stopPropagation()
                                                            resolveIssue(issue.id)
                                                        }}
                                                        className="btn-modern btn-success w-full mt-3"
                                                    >
                                                        <CheckCircle className="w-4 h-4" />
                                                        Mark as Resolved
                                                    </button>
                                                )}
                                            </div>
                                            <div className="message-stack">
                                                <h4 className="text-sm font-semibold mb-3">Messages ({messageCount})</h4>
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
                                        </div>
                                    )}
                                </div>
                            )
                        })}
                    </div>
                )}
            </div>
        )
    }

    return (
        <div className="app-shell">
            <div className="main-content">
                <div className="main-inner">
                    <div className="brand-bar glass-panel">
                        <div className="brand-cluster">
                            <img
                                src="/nixo-logo.png"
                                alt="Nixo Logo"
                                className="brand-logo"
                                onError={(e) => {
                                    e.target.style.display = 'none';
                                    e.target.nextElementSibling.style.display = 'flex';
                                }}
                            />
                            <div
                                className="brand-logo brand-fallback bg-gradient-to-br from-pink-500 to-purple-600"
                                style={{ display: 'none' }}
                            >
                                <TrendingUp className="w-5 h-5 text-white" />
                            </div>
                            <div>
                                <p className="brand-eyebrow">Customer Ops Console</p>
                                <div className="brand-title">Nixo</div>
                                <div className="brand-status">
                                    <span className={`status-dot ${isConnected ? 'online' : 'offline'}`} />
                                    <span>{isConnected ? 'Live connection' : 'Offline'}</span>
                                </div>
                            </div>
                        </div>
                        <button className="btn-modern btn-secondary brand-preferences">
                            <Settings className="w-4 h-4" />
                            Preferences
                        </button>
                    </div>

                    <div className="page-header glass-panel">
                        <div className="header-stack">
                            <div>
                                <p className="header-eyebrow">Live operations</p>
                                <h2 className="text-2xl font-bold mb-2">{heroCopy.title}</h2>
                                <p className="text-sm text-muted max-w-xl">{heroCopy.description}</p>
                                <div className="header-pills">
                                    <span className={`connection-chip ${isConnected ? 'online' : 'offline'}`}>
                                        <span className="chip-dot" />
                                        {isConnected ? 'Connected to Slack stream' : 'Connection lost'}
                                    </span>
                                    <span className="connection-chip neutral">
                                        {issues.length} total issues · {analytics.totalMessages} messages
                                    </span>
                                </div>
                            </div>
                            {showIssueFilters && (
                                <div className="header-actions">
                                    <div className="search-wrapper">
                                        <input
                                            className="search-input enhanced"
                                            type="text"
                                            placeholder="Search issues, ticket IDs or keywords"
                                            value={searchTerm}
                                            onChange={(event) => setSearchTerm(event.target.value)}
                                        />
                                    </div>
                                    <div className="pill-group">
                                        {classificationFilters.map((filter) => (
                                            <button
                                                key={filter.value}
                                                className={`pill ${classificationFilter === filter.value ? 'active' : ''}`}
                                                onClick={() => setClassificationFilter(filter.value)}
                                            >
                                                <div>
                                                    <span className="pill-label">{filter.label}</span>
                                                    <span className="pill-subtitle">{filter.subtitle}</span>
                                                </div>
                                                <span className="pill-count">
                                                    {filter.value === 'all'
                                                        ? issues.length
                                                        : classificationSummary[filter.value] || 0}
                                                </span>
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="view-nav">
                        {viewTabs.map(({ id, label, icon: Icon, count }) => (
                            <button
                                key={id}
                                className={`nav-chip ${activeView === id ? 'active' : ''}`}
                                onClick={() => handleViewChange(id)}
                            >
                                <Icon className="nav-chip-icon" />
                                <span>{label}</span>
                                <span className="nav-chip-count">{count}</span>
                            </button>
                        ))}
                    </div>

                    {/* Metrics */}
                    <div className="content-body">
                    {/* Metrics - Only show on Home/All Issues */}
                    {activeView === 'all' && (
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-8 animate-fade-in">
                            <div className="metric-card-modern surface-card">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="w-10 h-10 rounded-lg bg-[var(--status-warning-bg)] flex items-center justify-center">
                                        <Activity className="w-5 h-5 text-[var(--status-warning)]" />
                                    </div>
                                </div>
                                <div className="text-2xl font-bold mb-1">{activeIssues.length}</div>
                                <div className="text-sm text-muted">Active Issues</div>
                            </div>

                            <div className="metric-card-modern surface-card">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="w-10 h-10 rounded-lg bg-[var(--status-success-bg)] flex items-center justify-center">
                                        <CheckCircle className="w-5 h-5 text-[var(--status-success)]" />
                                    </div>
                                </div>
                                <div className="text-2xl font-bold mb-1">{resolvedIssues.length}</div>
                                <div className="text-sm text-muted">Resolved Today</div>
                            </div>

                            <div className="metric-card-modern surface-card">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="w-10 h-10 rounded-lg bg-[var(--status-info-bg)] flex items-center justify-center">
                                        <BarChart3 className="w-5 h-5 text-[var(--status-info)]" />
                                    </div>
                                </div>
                                <div className="text-2xl font-bold mb-1">{analytics.totalMessages}</div>
                                <div className="text-sm text-muted">Total Messages</div>
                            </div>

                            <div className="metric-card-modern surface-card">
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
                    {activeView === 'users' ? (
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
                                            <div className="card-modern p-16 text-center">
                                                <div className="w-24 h-24 bg-[var(--bg-tertiary)] rounded-full flex items-center justify-center mx-auto mb-6">
                                                    <Users className="w-12 h-12 text-[var(--text-tertiary)]" />
                                                </div>
                                                <h3 className="text-xl font-bold mb-2 text-[var(--text-primary)]">No users found</h3>
                                                <p className="text-[var(--text-secondary)] max-w-md mx-auto">
                                                    Users will appear here once issues are created and conversations start.
                                                </p>
                                            </div>
                                        </div>
                                    );
                                }

                                return Array.from(userMap.values()).map(user => (
                                    <div key={user.id} className="card-modern hover-lift user-card">
                                        <div className="user-card-header">
                                            <div
                                                className="avatar avatar-lg"
                                                style={{ background: getAvatarColor(user.id) }}
                                            >
                                                <span className="text-white text-lg">
                                                    {user.id[0].toUpperCase()}
                                                </span>
                                            </div>
                                            <div className="user-card-header-text">
                                                <h3 className="user-card-title">User {user.id}</h3>
                                                <p className="user-card-subtitle">
                                                    Last active {new Date(user.lastActive).toLocaleDateString([], {
                                                        month: 'short',
                                                        day: 'numeric',
                                                        hour: '2-digit',
                                                        minute: '2-digit'
                                                    })}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="user-card-meta">
                                            <div className="user-card-stat">
                                                <span className="meta-label">Messages</span>
                                                <span className="stat-value">{user.messageCount}</span>
                                            </div>
                                            <div className="user-card-stat">
                                                <span className="meta-label">Issues</span>
                                                <span className="stat-value">{user.issueCount}</span>
                                            </div>
                                        </div>
                                    </div>
                                ));
                            })()}
                        </div>
                    ) : (
                        renderIssueCards(filteredIssues)
                    )}
                </div>
            </div>
        </div>
    </div>
    )
}

export default App
