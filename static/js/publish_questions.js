document.addEventListener('DOMContentLoaded', () => {
    const subjectSelect = document.getElementById('subject-select');
    const subjectCodeInput = document.getElementById('subject-code');
    const questionsContainer = document.getElementById('questions-container');
    const emptyBuilder = document.getElementById('empty-builder');
    const questionCountBadge = document.getElementById('question-count-badge');
    const previewContainer = document.getElementById('preview-container');
    const previewCount = document.getElementById('preview-count');

    // Searchable Select DOM elements
    const subjectSelectContainer = document.getElementById('subject-select-container');
    const subjectSelectTrigger = document.getElementById('subject-select-trigger');
    const subjectSearchInput = document.getElementById('subject-search-input');
    const dropdownOptionsList = document.getElementById('dropdown-options-list');
    const sidebarSubjectSearch = document.getElementById('sidebar-subject-search');
    const liveStatsList = document.getElementById('live-stats-list');

    let questionIndex = 0;

    // Searchable Select Logic
    if (subjectSelectTrigger) {
        subjectSelectTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            subjectSelectContainer.classList.toggle('open');
            if (subjectSelectContainer.classList.contains('open') && subjectSearchInput) {
                subjectSearchInput.focus();
                subjectSearchInput.value = '';
                filterDropdownOptions('');
            }
        });
    }

    if (subjectSearchInput) {
        subjectSearchInput.addEventListener('input', (e) => {
            filterDropdownOptions(e.target.value);
        });
        subjectSearchInput.addEventListener('click', (e) => {
            e.stopPropagation(); // prevent dropdown close
        });
    }

    // Click outside to close dropdown
    document.addEventListener('click', () => {
        if (subjectSelectContainer) {
            subjectSelectContainer.classList.remove('open');
        }
    });

    // Custom dropdown options click handlers
    if (dropdownOptionsList) {
        dropdownOptionsList.addEventListener('click', (e) => {
            const option = e.target.closest('.dropdown-option');
            if (!option) return;

            const name = option.dataset.value;
            const code = option.dataset.code;
            const id = option.dataset.id;

            selectDropdownOption(name, code, id);
            subjectSelectContainer.classList.remove('open');
        });
    }

    function filterDropdownOptions(query) {
        const q = query.trim().toLowerCase();
        const options = dropdownOptionsList.querySelectorAll('.dropdown-option');
        let visibleCount = 0;

        options.forEach(opt => {
            if (opt.classList.contains('empty-option')) {
                opt.style.display = q === '' ? 'block' : 'none';
                return;
            }
            const text = opt.innerText.toLowerCase();
            if (text.includes(q)) {
                opt.style.display = 'block';
                visibleCount++;
            } else {
                opt.style.display = 'none';
            }
        });
    }

    function selectDropdownOption(name, code, id) {
        // Update trigger text
        const triggerText = subjectSelectTrigger.querySelector('.trigger-text');
        if (name) {
            triggerText.textContent = code ? `${name} (${code})` : name;
            triggerText.style.color = 'var(--ink)';
            subjectCodeInput.value = code || '';
        } else {
            triggerText.textContent = 'Select a subject...';
            triggerText.style.color = '';
            subjectCodeInput.value = '';
        }

        // Update hidden native select
        if (subjectSelect) {
            subjectSelect.value = name;
            // Update selected index to ensure change event data is accessible
            for (let i = 0; i < subjectSelect.options.length; i++) {
                if (subjectSelect.options[i].value === name) {
                    subjectSelect.selectedIndex = i;
                    break;
                }
            }
        }

        // Highlight active dropdown option
        const options = dropdownOptionsList.querySelectorAll('.dropdown-option');
        options.forEach(opt => {
            if (opt.dataset.value === name) {
                opt.classList.add('selected');
            } else {
                opt.classList.remove('selected');
            }
        });
    }

    // Sidebar Live Question Bank Filter
    if (sidebarSubjectSearch && liveStatsList) {
        sidebarSubjectSearch.addEventListener('input', (e) => {
            const query = e.target.value.trim().toLowerCase();
            const items = liveStatsList.querySelectorAll('.live-stat-item');
            
            items.forEach(item => {
                const subject = (item.dataset.subject || '').toLowerCase();
                if (subject.includes(query)) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
        });
    }

    document.getElementById('add-question-btn')?.addEventListener('click', () => {
        if (!getSelectedSubject() || !getSelectedSubject().name) {
            showToast('Please select a subject from the collection first.');
            return;
        }
        addQuestionCard();
    });

    document.getElementById('load-existing-btn')?.addEventListener('click', loadExistingQuestions);
    document.getElementById('submit-all-btn')?.addEventListener('click', publishQuestions);
    document.getElementById('clear-subject-btn')?.addEventListener('click', clearSubjectQuestions);
    document.getElementById('clear-all-btn')?.addEventListener('click', clearAllQuestions);

    document.querySelectorAll('.live-stat-item').forEach(item => {
        item.addEventListener('click', () => {
            setSubjectSelection(item.dataset.subject);
            loadExistingQuestions();
        });
    });

    function getSelectedSubject() {
        if (!subjectSelect) return { name: '', id: '', code: '' };
        const selected = subjectSelect.selectedOptions[0];
        return {
            name: subjectSelect.value.trim(),
            id: selected?.dataset.id || '',
            code: selected?.dataset.code || '',
        };
    }

    function setSubjectSelection(subjectName) {
        const option = Array.from(subjectSelect.options).find(opt => opt.value === subjectName);
        if (!option) return;

        const code = option.dataset.code || '';
        const id = option.dataset.id || '';
        selectDropdownOption(subjectName, code, id);
    }

    function addQuestionCard(data = {}) {
        questionIndex += 1;
        const cardId = `question-${questionIndex}`;
        const card = document.createElement('div');
        card.className = 'question-card';
        card.dataset.id = cardId;
        card.innerHTML = `
            <div class="question-card-header">
                <span class="question-number">Question <span class="q-num">${questionsContainer.children.length + 1}</span></span>
                <button type="button" class="btn btn-outline btn-sm remove-question-btn">Remove</button>
            </div>
            <div class="form-group">
                <label>Question Text</label>
                <textarea class="question-text" rows="3" placeholder="Enter the question...">${escapeHtml(data.question_text || '')}</textarea>
            </div>
            <div class="options-grid">
                ${['A', 'B', 'C', 'D'].map(key => `
                    <div class="option-row">
                        <label class="option-label">${key}</label>
                        <input type="text" class="option-input" data-option="${key}" placeholder="Option ${key}" value="${escapeAttr(data.options?.[key] || '')}">
                        <label class="correct-radio">
                            <input type="radio" name="correct-${cardId}" value="${key}" ${data.correct_answer === key ? 'checked' : ''}>
                            <span>Correct</span>
                        </label>
                    </div>
                `).join('')}
            </div>
        `;

        // Style helper for correct answer selection styling
        card.querySelectorAll('input[type="radio"]').forEach(radio => {
            const optionRow = radio.closest('.option-row');
            const labelContainer = radio.closest('.correct-radio');
            if (radio.checked) {
                optionRow.classList.add('has-correct-selected');
                labelContainer.classList.add('checked-active');
            }
            
            radio.addEventListener('change', () => {
                card.querySelectorAll('.option-row').forEach(row => row.classList.remove('has-correct-selected'));
                card.querySelectorAll('.correct-radio').forEach(lbl => lbl.classList.remove('checked-active'));
                
                if (radio.checked) {
                    optionRow.classList.add('has-correct-selected');
                    labelContainer.classList.add('checked-active');
                }
            });
        });

        card.querySelector('.remove-question-btn').addEventListener('click', () => {
            card.style.opacity = '0';
            card.style.transform = 'scale(0.95)';
            card.style.transition = 'all 0.2s ease';
            setTimeout(() => {
                card.remove();
                renumberQuestions();
                updateBuilderState();
            }, 200);
        });

        questionsContainer.appendChild(card);
        updateBuilderState();
    }

    function renumberQuestions() {
        questionsContainer.querySelectorAll('.question-card').forEach((card, index) => {
            card.querySelector('.q-num').textContent = index + 1;
        });
    }

    function updateBuilderState() {
        const count = questionsContainer.querySelectorAll('.question-card').length;
        questionCountBadge.textContent = `${count} question${count === 1 ? '' : 's'}`;
        emptyBuilder.style.display = count ? 'none' : 'block';
        questionsContainer.style.display = count ? 'flex' : 'none';
    }

    function collectQuestions() {
        const questions = [];
        questionsContainer.querySelectorAll('.question-card').forEach(card => {
            const options = {};
            card.querySelectorAll('.option-input').forEach(input => {
                options[input.dataset.option] = input.value.trim();
            });
            const correctInput = card.querySelector('input[type="radio"]:checked');
            questions.push({
                question_text: card.querySelector('.question-text').value.trim(),
                options,
                correct_answer: correctInput ? correctInput.value : '',
            });
        });
        return questions;
    }

    async function loadExistingQuestions() {
        const subject = getSelectedSubject();
        if (!subject.name) {
            showToast('Select a subject from the Subject collection to load existing questions.');
            return;
        }

        try {
            const res = await fetch(`/api/live-questions?subject=${encodeURIComponent(subject.name)}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to load questions.');

            questionsContainer.innerHTML = '';
            questionIndex = 0;
            data.questions.forEach(question => addQuestionCard(question));
            renderPreview(data.questions, subject.name);
            showToast(`Loaded ${data.count} question(s) for ${subject.name}.`);
        } catch (error) {
            showToast(error.message);
        }
    }

    async function publishQuestions() {
        const subject = getSelectedSubject();
        const questions = collectQuestions();

        if (!subject.name) {
            showToast('Please select a subject from the Subject collection.');
            return;
        }
        if (!questions.length) {
            showToast('Add at least one question before publishing.');
            return;
        }

        const confirmMessage = `Publish ${questions.length} question(s) for "${subject.name}"?\n\nThis will replace any existing live questions for this subject.`;
        if (!confirm(confirmMessage)) return;

        try {
            const res = await fetch('/api/live-questions/publish', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    subject: subject.name,
                    subject_id: subject.id,
                    questions,
                }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to publish questions.');

            renderPreview(questions.map((q, i) => ({
                question_number: i + 1,
                question_text: q.question_text,
                options: q.options,
                correct_answer: q.correct_answer,
            })), subject.name);

            showToast(data.message);
            location.reload();
        } catch (error) {
            showToast(error.message);
        }
    }

    async function clearSubjectQuestions() {
        const subject = getSelectedSubject();
        if (!subject.name) {
            showToast('Select a subject from the Subject collection to clear its questions.');
            return;
        }
        if (!confirm(`Clear all live questions for "${subject.name}"?`)) return;

        try {
            const res = await fetch('/api/live-questions/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subject: subject.name }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to clear questions.');

            questionsContainer.innerHTML = '';
            updateBuilderState();
            previewContainer.innerHTML = '<p class="muted-note">No live questions for this subject.</p>';
            previewCount.textContent = '0';
            showToast(data.message);
            location.reload();
        } catch (error) {
            showToast(error.message);
        }
    }

    async function clearAllQuestions() {
        if (!confirm('Clear ALL live questions from the database? This cannot be undone.')) return;

        try {
            const res = await fetch('/api/live-questions/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clear_all: true }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to clear all questions.');

            questionsContainer.innerHTML = '';
            updateBuilderState();
            previewContainer.innerHTML = '<p class="muted-note">No live questions published yet.</p>';
            previewCount.textContent = '0';
            showToast(data.message);
            location.reload();
        } catch (error) {
            showToast(error.message);
        }
    }

    function renderPreview(questions, subject) {
        previewCount.textContent = questions.length;
        if (!questions.length) {
            previewContainer.innerHTML = '<p class="muted-note">No live questions for this subject.</p>';
            return;
        }

        previewContainer.innerHTML = questions.map(question => `
            <div class="preview-item">
                <div class="preview-q">Q${question.question_number}. ${escapeHtml(question.question_text)}</div>
                <ul class="preview-options">
                    ${['A', 'B', 'C', 'D'].map(key => `
                        <li class="${question.correct_answer === key ? 'correct' : ''}">
                            <strong>${key}.</strong> ${escapeHtml(question.options?.[key] || '')}
                        </li>
                    `).join('')}
                </ul>
            </div>
        `).join('');

        previewContainer.insertAdjacentHTML('afterbegin', `<div class="preview-subject">${escapeHtml(subject)}</div>`);
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function escapeAttr(value) {
        return escapeHtml(value).replace(/`/g, '&#96;');
    }

    updateBuilderState();
});
