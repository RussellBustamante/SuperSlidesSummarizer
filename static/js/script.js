document.addEventListener('DOMContentLoaded', function() {
    let pdfDoc = null;
    let pageNum = 1;
    let pageRendering = false;
    let pageNumPending = null;
    const canvas = document.getElementById('pdfCanvas');
    const ctx = canvas.getContext('2d');
    let slideTexts = {};

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

    // Update slide text in the right panel
    function updateSlideText(slideNumber) {
        const slideTextElement = document.getElementById('slideText');
        slideTextElement.textContent = slideTexts[slideNumber] || `No text available for slide ${slideNumber}`;
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

    // Handle Gemini API calls
    const submitBtn = document.getElementById('submitBtn');
    const buttonText = submitBtn.querySelector('.button-text');
    const loadingSpinner = submitBtn.querySelector('.loading-spinner');
    const responseText = document.getElementById('responseText');
    const userInput = document.getElementById('userInput');

    function setLoading(isLoading) {
        submitBtn.disabled = isLoading;
        buttonText.style.display = isLoading ? 'none' : 'block';
        loadingSpinner.style.display = isLoading ? 'block' : 'none';
        if (isLoading) {
            responseText.classList.add('loading');
            responseText.textContent = 'Asking Gemini...';
        } else {
            responseText.classList.remove('loading');
        }
    }

    async function askGemini(question) {
        try {
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

            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Failed to get response from Gemini');
            }

            responseText.classList.remove('error');
            responseText.textContent = data.response;

        } catch (error) {
            console.error('Error:', error);
            responseText.classList.add('error');
            responseText.textContent = 'Error: ' + error.message;
        }
    }

    // Submit button click handler
    submitBtn.addEventListener('click', async function() {
        const question = userInput.value.trim();
        if (!question) {
            responseText.classList.add('error');
            responseText.textContent = 'Please enter a question';
            return;
        }

        setLoading(true);
        await askGemini(question);
        setLoading(false);
    });

    // Also submit on Enter key (if Shift isn't pressed)
    userInput.addEventListener('keydown', async function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitBtn.click();
        }
    });
});
