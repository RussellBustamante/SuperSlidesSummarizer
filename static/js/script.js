document.addEventListener('DOMContentLoaded', function() {
    let pdfDoc = null;
    let pageNum = 1;
    let pageRendering = false;
    let pageNumPending = null;
    const canvas = document.getElementById('pdfCanvas');
    const ctx = canvas.getContext('2d');
    let slideTexts = {};

    // Load marked.js for markdown support
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';
    document.head.appendChild(script);

    // Handle Gemini API calls
    const submitBtn = document.getElementById('submitBtn');
    const userInput = document.getElementById('userInput');
    const buttonText = submitBtn.querySelector('.button-text');
    const loadingSpinner = submitBtn.querySelector('.loading-spinner');
    const responseText = document.getElementById('responseText');

    function setLoading(isLoading) {
        submitBtn.disabled = isLoading;
        buttonText.style.display = isLoading ? 'none' : 'inline';
        loadingSpinner.style.display = isLoading ? 'inline' : 'none';
    }

    async function askGemini(question) {
        console.log('askGemini called with question:', question);
        try {
            console.log('Making fetch request to /ask_gemini');
            const response = await fetch('/ask_gemini', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    question: question,
                    currentSlide: pageNum
                })
            });

            console.log('Got response from /ask_gemini');
            const data = await response.json();
            console.log('Response data:', data);
            
            if (!data.success) {
                throw new Error(data.error || 'Failed to get response from Gemini');
            }

            return data;

        } catch (error) {
            console.error('Error in askGemini:', error);
            throw error;
        }
    }

    // Submit button click handler
    submitBtn.addEventListener('click', async function() {
        console.log('Submit button clicked');
        const question = userInput.value.trim();
        console.log('Question:', question);
        if (!question) {
            console.log('No question provided');
            return;
        }

        setLoading(true);
        responseText.textContent = 'Thinking...';

        try {
            console.log('Sending request to Gemini...');
            const response = await askGemini(question);
            console.log('Got response:', response);
            if (response.success) {
                responseText.innerHTML = marked.parse(response.response);
            } else {
                responseText.innerHTML = marked.parse(`**Error:** ${response.error}`);
            }
        } catch (error) {
            console.error('Error in submit handler:', error);
            responseText.innerHTML = marked.parse(`**Error:** ${error.message}`);
        } finally {
            setLoading(false);
        }
    });

    // Also submit on Enter key (if Shift isn't pressed)
    userInput.addEventListener('keydown', async function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitBtn.click();
        }
    });

    // Fetch slide texts from server
    fetch('/slide_texts')
        .then(response => response.json())
        .then(data => {
            slideTexts = data;
            updateSlideText(pageNum);
        });

    // Load the PDF
    pdfjsLib.getDocument('/pdf/03-storage1.pdf').promise.then(function(pdfDoc_) {
        pdfDoc = pdfDoc_;
        document.getElementById('pageCount').textContent = pdfDoc.numPages;
        
        // Initial page render
        renderPage(pageNum);
    });

    function renderPage(num) {
        pageRendering = true;
        
        // Update page counter
        document.getElementById('pageNum').textContent = num;
        
        // Update slide text
        updateSlideText(num);

        // Render PDF page
        pdfDoc.getPage(num).then(function(page) {
            const viewport = page.getViewport({scale: 1.5});
            canvas.height = viewport.height;
            canvas.width = viewport.width;

            const renderContext = {
                canvasContext: ctx,
                viewport: viewport
            };
            
            return page.render(renderContext).promise;
        }).then(function() {
            pageRendering = false;
            if (pageNumPending !== null) {
                renderPage(pageNumPending);
                pageNumPending = null;
            }
        });
    }

    function queueRenderPage(num) {
        if (pageRendering) {
            pageNumPending = num;
        } else {
            renderPage(num);
        }
    }

    function onPrevPage() {
        if (pageNum <= 1) {
            // Wrap to last page
            pageNum = pdfDoc.numPages;
        } else {
            pageNum--;
        }
        queueRenderPage(pageNum);
    }

    function onNextPage() {
        if (pageNum >= pdfDoc.numPages) {
            // Wrap to first page
            pageNum = 1;
        } else {
            pageNum++;
        }
        queueRenderPage(pageNum);
    }

    function findRelatedSlides(currentSlide) {
        const currentSummary = slideTexts[currentSlide]?.summary;
        if (!currentSummary) return [currentSlide];
        
        // Find all slides that share the same summary
        return Object.entries(slideTexts)
            .filter(([_, data]) => data.summary === currentSummary)
            .map(([num, _]) => parseInt(num))
            .sort((a, b) => a - b);
    }

    function updateSlideText(slideNumber) {
        const slideText = document.getElementById('slideText');
        const summaryTitle = document.getElementById('summaryTitle');
        const slideKey = slideNumber.toString();
        
        if (slideTexts[slideKey]) {
            const slideData = slideTexts[slideKey];
            if (typeof slideData === 'string') {
                // Handle old format
                slideText.innerHTML = marked.parse(slideData);
                summaryTitle.textContent = 'Summary for slides...';
            } else {
                // Handle new format with summary
                const relatedSlides = findRelatedSlides(slideKey);
                const slideRange = relatedSlides.length > 1 
                    ? `Slides ${relatedSlides.join(', ')}`
                    : `Slide ${slideKey}`;
                
                summaryTitle.textContent = `Summary for ${slideRange}`;
                slideText.innerHTML = marked.parse(slideData.summary || '');
            }
        } else {
            slideText.textContent = 'No text available for this slide.';
            summaryTitle.textContent = 'Summary for slides...';
        }
    }

    // Button event listeners
    document.getElementById('prevPage').addEventListener('click', onPrevPage);
    document.getElementById('nextPage').addEventListener('click', onNextPage);
    
    // Keyboard navigation
    document.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowLeft') {
            onPrevPage();
        } else if (e.key === 'ArrowRight') {
            onNextPage();
        }
    });

    // Theme toggle functionality
    const themeToggle = document.getElementById('themeToggle');
    
    // Check for saved theme preference or default to 'light'
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    themeToggle.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    });

    // Process PDF button handler
    const uploadBtn = document.getElementById('uploadBtn');
    uploadBtn.addEventListener('click', async function() {
        try {
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Processing...';
            
            const response = await fetch('/process_pdf', {
                method: 'POST'
            });
            
            const data = await response.json();
            if (data.success) {
                alert('PDF processing started! The summaries will be updated shortly. This could take 1-4 minutes depending on the PDF size. Check your terminal prints.');
                // Reload slide texts after a short delay
                setTimeout(() => {
                    loadSlideTexts();
                }, 2000);
            } else {
                throw new Error(data.error || 'Failed to process PDF');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error: ' + error.message);
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<span class="button-icon">📤</span>Upload Slides to Summarize';
        }
    });

    document.getElementById('uploadForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Clear existing slides and reset progress immediately
        document.getElementById('slideContainer').innerHTML = '';
        document.getElementById('progressBar').style.width = '0%';
        document.getElementById('progressBar').style.display = 'block';
        
        const formData = new FormData(this);
        
        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error('Upload failed');
            }
            
            // Start checking progress
            checkProgress();
            
        } catch (error) {
            console.error('Error:', error);
            alert('Upload failed: ' + error.message);
        }
    });

    async function checkProgress() {
        try {
            const response = await fetch('/progress');
            const data = await response.json();
            
            // Update progress bar
            const progressBar = document.getElementById('progressBar');
            progressBar.style.width = data.progress + '%';
            
            if (data.progress < 100) {
                // Check again in 1 second
                setTimeout(checkProgress, 1000);
            } else {
                // Processing complete - refresh the page
                window.location.reload();
            }
        } catch (error) {
            console.error('Error checking progress:', error);
        }
    }

    function updateSlideContainer(slideTexts) {
        const container = document.getElementById('slideContainer');
        container.innerHTML = ''; // Clear existing content
        
        // Sort slide numbers numerically
        const slideNumbers = Object.keys(slideTexts).sort((a, b) => parseInt(a) - parseInt(b));
        
        for (const slideNum of slideNumbers) {
            const slideData = slideTexts[slideNum];
            const slideDiv = document.createElement('div');
            slideDiv.className = 'slide-box';
            
            const titleInput = document.createElement('input');
            titleInput.type = 'text';
            titleInput.className = 'slide-title';
            titleInput.value = slideData.title || '';
            titleInput.placeholder = 'Slide Title';
            
            const summaryTextarea = document.createElement('textarea');
            summaryTextarea.className = 'slide-summary';
            summaryTextarea.value = slideData.summary || '';
            summaryTextarea.placeholder = 'Slide Summary';
            
            const slideLabel = document.createElement('div');
            slideLabel.className = 'slide-label';
            slideLabel.textContent = `Slide ${slideNum}`;
            
            slideDiv.appendChild(slideLabel);
            slideDiv.appendChild(titleInput);
            slideDiv.appendChild(summaryTextarea);
            container.appendChild(slideDiv);
        }
    }
});
