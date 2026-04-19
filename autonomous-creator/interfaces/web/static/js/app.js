/**
 * Autonomous Creator Web UI
 * 프론트엔드 로직
 */

// API 기본 URL
const API_BASE = '/api';

// 상태 관리
const state = {
    currentStoryId: null,
    isGenerating: false,
    websocket: null,
    stories: []
};

// DOM 요소
const elements = {
    storyForm: document.getElementById('story-form'),
    titleInput: document.getElementById('title'),
    contentInput: document.getElementById('content'),
    languageSelect: document.getElementById('language'),
    videoModeSelect: document.getElementById('video-mode'),
    keywordsInput: document.getElementById('keywords'),
    saveBtn: document.getElementById('save-btn'),
    generateBtn: document.getElementById('generate-btn'),
    progressSection: document.getElementById('progress-section'),
    progressFill: document.getElementById('progress-fill'),
    progressStep: document.getElementById('progress-step'),
    progressPercent: document.getElementById('progress-percent'),
    resultSection: document.getElementById('result-section'),
    resultVideo: document.getElementById('result-video'),
    videoDuration: document.getElementById('video-duration'),
    videoCost: document.getElementById('video-cost'),
    downloadBtn: document.getElementById('download-btn'),
    newVideoBtn: document.getElementById('new-video-btn'),
    storyList: document.getElementById('story-list'),
    toastContainer: document.getElementById('toast-container')
};

// ============================================
// 유틸리티 함수
// ============================================

/**
 * 토스트 알림 표시
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

/**
 * API 요청 헬퍼
 */
async function apiRequest(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * 단계별 진행 상태 업데이트
 */
function updateStepIndicators(currentStep) {
    const steps = ['script', 'audio', 'image', 'video', 'final'];
    const stepMap = {
        '초기화': -1,
        '스크립트 생성 중': 0,
        '음성 생성 중': 1,
        '이미지 생성 중': 2,
        '비디오 생성 중': 3,
        '영상 합성 중': 3,
        '마무리 중': 4,
        '완료': 4
    };

    const currentIndex = stepMap[currentStep] ?? -1;

    document.querySelectorAll('.progress-steps .step').forEach((el, index) => {
        el.classList.remove('active', 'completed');
        if (index < currentIndex) {
            el.classList.add('completed');
        } else if (index === currentIndex) {
            el.classList.add('active');
        }
    });
}

// ============================================
// WebSocket 연결
// ============================================

/**
 * WebSocket 연결 초기화
 */
function initWebSocket() {
    const clientId = 'client_' + Date.now();
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/pipeline/ws/${clientId}`;

    state.websocket = new WebSocket(wsUrl);

    state.websocket.onopen = () => {
        console.log('WebSocket connected');
    };

    state.websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    state.websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    state.websocket.onclose = () => {
        console.log('WebSocket disconnected');
        // 재연결 시도
        setTimeout(initWebSocket, 3000);
    };
}

/**
 * WebSocket 메시지 처리
 */
function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'connected':
            console.log('WebSocket confirmed:', data.message);
            break;

        case 'progress':
            updateProgress(data);
            break;

        case 'completed':
            handleGenerationComplete(data);
            break;

        case 'error':
            showToast(data.message, 'error');
            state.isGenerating = false;
            break;

        case 'ping':
            // pong 응답
            if (state.websocket?.readyState === WebSocket.OPEN) {
                state.websocket.send(JSON.stringify({ type: 'pong' }));
            }
            break;
    }
}

/**
 * 진행 상황 업데이트
 */
function updateProgress(data) {
    elements.progressSection.style.display = 'block';

    const progress = data.progress || 0;
    elements.progressFill.style.width = `${progress}%`;
    elements.progressPercent.textContent = `${progress}%`;
    elements.progressStep.textContent = data.current_step || 'Processing...';

    updateStepIndicators(data.current_step);
}

/**
 * 생성 완료 처리
 */
function handleGenerationComplete(data) {
    state.isGenerating = false;
    elements.generateBtn.disabled = false;

    if (data.output_paths && data.output_paths.length > 0) {
        elements.resultSection.style.display = 'block';
        elements.resultVideo.src = data.output_paths[0];
        showToast('Video generation completed!', 'success');
    }
}

// ============================================
// 스토리 관리
// ============================================

/**
 * 스토리 목록 로드
 */
async function loadStories() {
    try {
        const stories = await apiRequest('/stories?limit=20');
        state.stories = stories;
        renderStoryList(stories);
    } catch (error) {
        elements.storyList.innerHTML = '<li class="loading">Failed to load stories</li>';
    }
}

/**
 * 스토리 목록 렌더링
 */
function renderStoryList(stories) {
    if (stories.length === 0) {
        elements.storyList.innerHTML = '<li class="loading">No saved stories</li>';
        return;
    }

    elements.storyList.innerHTML = stories.map(story => `
        <li data-id="${story.id}">
            <div class="story-title">${escapeHtml(story.title)}</div>
            <div class="story-meta">${story.language} - ${formatDate(story.created_at)}</div>
        </li>
    `).join('');

    // 클릭 이벤트 바인딩
    elements.storyList.querySelectorAll('li[data-id]').forEach(li => {
        li.addEventListener('click', () => loadStory(li.dataset.id));
    });
}

/**
 * 스토리 로드
 */
async function loadStory(storyId) {
    try {
        const story = await apiRequest(`/stories/${storyId}`);

        elements.titleInput.value = story.title;
        elements.contentInput.value = story.content;
        elements.languageSelect.value = story.language;
        elements.videoModeSelect.value = story.video_mode;
        elements.keywordsInput.value = story.keywords.join(', ');

        state.currentStoryId = story.id;
        elements.generateBtn.disabled = false;

        showToast('Story loaded', 'success');
    } catch (error) {
        showToast('Failed to load story', 'error');
    }
}

/**
 * 스토리 저장
 */
async function saveStory() {
    const storyData = {
        title: elements.titleInput.value.trim(),
        content: elements.contentInput.value.trim(),
        language: elements.languageSelect.value,
        video_mode: elements.videoModeSelect.value,
        keywords: elements.keywordsInput.value
            .split(',')
            .map(k => k.trim())
            .filter(k => k)
    };

    if (!storyData.title || !storyData.content) {
        showToast('Please fill in title and content', 'warning');
        return;
    }

    try {
        const story = await apiRequest('/stories', {
            method: 'POST',
            body: JSON.stringify(storyData)
        });

        state.currentStoryId = story.id;
        elements.generateBtn.disabled = false;

        showToast('Story saved!', 'success');
        loadStories();
    } catch (error) {
        showToast('Failed to save story: ' + error.message, 'error');
    }
}

// ============================================
// 영상 생성
// ============================================

/**
 * 영상 생성 요청
 */
async function generateVideo() {
    if (!state.currentStoryId) {
        showToast('Please save a story first', 'warning');
        return;
    }

    if (state.isGenerating) {
        showToast('Generation already in progress', 'warning');
        return;
    }

    state.isGenerating = true;
    elements.generateBtn.disabled = true;
    elements.progressSection.style.display = 'block';
    elements.resultSection.style.display = 'none';

    // 진행 상태 초기화
    elements.progressFill.style.width = '0%';
    elements.progressPercent.textContent = '0%';
    elements.progressStep.textContent = 'Starting...';
    updateStepIndicators('');

    try {
        const result = await apiRequest(`/pipeline/${state.currentStoryId}/generate`, {
            method: 'POST',
            body: JSON.stringify({
                output_dir: 'outputs'
            })
        });

        showToast('Video generation started', 'success');

        // 상태 폴링 (WebSocket 백업)
        pollGenerationStatus(state.currentStoryId);

    } catch (error) {
        state.isGenerating = false;
        elements.generateBtn.disabled = false;
        showToast('Failed to start generation: ' + error.message, 'error');
    }
}

/**
 * 생성 상태 폴링 (WebSocket 백업)
 */
async function pollGenerationStatus(storyId) {
    const poll = async () => {
        if (!state.isGenerating) return;

        try {
            const status = await apiRequest(`/pipeline/${storyId}/status`);

            updateProgress({
                progress: status.progress,
                current_step: status.current_step
            });

            if (status.status === 'completed') {
                handleGenerationComplete({
                    output_paths: status.output_paths
                });
            } else if (status.status === 'failed') {
                state.isGenerating = false;
                elements.generateBtn.disabled = false;
                showToast('Generation failed: ' + status.error_message, 'error');
            } else {
                // 계속 폴링
                setTimeout(poll, 2000);
            }
        } catch (error) {
            console.error('Polling error:', error);
            setTimeout(poll, 3000);
        }
    };

    poll();
}

// ============================================
// 이벤트 핸들러
// ============================================

/**
 * 새 영상 만들기 (폼 초기화)
 */
function resetForm() {
    elements.storyForm.reset();
    state.currentStoryId = null;
    state.isGenerating = false;
    elements.generateBtn.disabled = true;
    elements.progressSection.style.display = 'none';
    elements.resultSection.style.display = 'none';
}

/**
 * 다운로드
 */
function downloadVideo() {
    if (elements.resultVideo.src) {
        const a = document.createElement('a');
        a.href = elements.resultVideo.src;
        a.download = 'generated_video.mp4';
        a.click();
    }
}

// ============================================
// 헬퍼 함수
// ============================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString();
}

// ============================================
// 초기화
// ============================================

function init() {
    // 이벤트 리스너 등록
    elements.saveBtn.addEventListener('click', saveStory);
    elements.generateBtn.addEventListener('click', generateVideo);
    elements.newVideoBtn.addEventListener('click', resetForm);
    elements.downloadBtn.addEventListener('click', downloadVideo);

    // 폼 입력 시 생성 버튼 활성화
    elements.contentInput.addEventListener('input', () => {
        if (elements.contentInput.value.trim() && elements.titleInput.value.trim()) {
            elements.generateBtn.disabled = !state.currentStoryId;
        }
    });

    // 스토리 목록 로드
    loadStories();

    // WebSocket 초기화
    initWebSocket();

    console.log('Autonomous Creator Web UI initialized');
}

// DOM 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', init);
