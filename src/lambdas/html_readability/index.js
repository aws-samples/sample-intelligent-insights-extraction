const { Readability } = require('@mozilla/readability');
const { JSDOM } = require('jsdom');
const { S3Client, GetObjectCommand } = require('@aws-sdk/client-s3');



// Configure logging
const LOG_LEVEL = process.env.LOG_LEVEL || 'DEBUG';
const logger = {
  debug: (message) => { if (LOG_LEVEL === 'DEBUG') console.log(`DEBUG: ${message}`); },
  info: (message) => console.log(`INFO: ${message}`),
  warn: (message) => console.warn(`WARN: ${message}`),
  error: (message) => console.error(`ERROR: ${message}`)
};

/**
 * Fallback method to extract text nodes from HTML
 * 
 * @param {string} html - Raw HTML content
 * @returns {object} - Basic content extraction with text nodes
 */
function fallbackContentExtraction(html) {
  try {
    const dom = new JSDOM(html);
    const document = dom.window.document;
    
    // Extract title
    const titleElement = document.querySelector('title');
    const title = titleElement ? titleElement.textContent.trim() : 'Untitled';
    
    // Get all text nodes
    const walker = document.createTreeWalker(
      document.body || document,
      dom.window.NodeFilter.SHOW_TEXT,
      null,
      false
    );
    
    let textContent = '';
    let node;
    while (node = walker.nextNode()) {
      const text = node.textContent.trim();
      if (text) {
        textContent += text + ' ';
      }
    }
    
    textContent = textContent.trim();
    const excerpt = textContent.length > 200 ? textContent.substring(0, 200) + '...' : textContent;
    
    return {
      title: title,
      content: `<p>${textContent}</p>`,
      textContent: textContent,
      excerpt: excerpt,
      byline: null,
      dir: null,
      siteName: null,
      length: textContent.length,
      success: true,
      fallback: true
    };
  } catch (error) {
    logger.error(`Fallback content extraction failed: ${error.message}`);
    throw error;
  }
}






/**
 * Process HTML content using Mozilla's Readability
 * 
 * @param {string} html - Raw HTML content
 * @returns {object} - Processed content object
 */
async function processHtmlContent(html) {
  try {
    const dom = new JSDOM(html, {
      url: "https://example.org/",
      contentType: "text/html",
      includeNodeLocations: false,
      resources: "usable",
      runScripts: "outside-only",
      pretendToBeVisual: false,
      features: {
        FetchExternalResources: false,
        ProcessExternalResources: false,
        SkipExternalResources: true
      }
    });
    
    const reader = new Readability(dom.window.document);
    const article = reader.parse();
    
    if (!article) {
      logger.warn('Readability failed to parse content, trying fallback method...');
      return fallbackContentExtraction(html);
    }
    
    logger.info(`Successfully processed article with Readability: "${article.title}" (${article.length} characters)`);
    
    return {
      title: article.title,
      content: article.content,
      textContent: article.textContent,
      excerpt: article.excerpt,
      byline: article.byline,
      dir: article.dir,
      siteName: article.siteName,
      length: article.length,
      success: true,
      fallback: false
    };
    
  } catch (error) {
    logger.warn(`JSDOM/Readability failed: ${error.message}. Trying fallback method...`);
    return fallbackContentExtraction(html);
  }
}


/**
 * Lambda handler function
 * 
 * @param {object} event - Lambda event
 * @param {object} context - Lambda context
 * @returns {Promise<object>} - Response
 */
exports.handler = async (event, context) => {
  logger.info(`Received event: ${JSON.stringify(event)}`);
  
  try {
    const s3_bucket = event.s3_bucket;
    const s3_key = event.s3_key;
    
    // Validate required S3 parameters
    if (!s3_bucket || !s3_key) {
      throw new Error('Missing required parameters: s3_bucket and s3_key are required');
    }
    
    // Read HTML content from S3
    const s3Client = new S3Client({ region: process.env.AWS_REGION || 'us-east-1' });
    const getObjectCommand = new GetObjectCommand({
      Bucket: s3_bucket,
      Key: s3_key
    });
    
    let htmlContent;
    try {
      const s3Response = await s3Client.send(getObjectCommand);
      htmlContent = await s3Response.Body.transformToString();

      logger.info(`Successfully read HTML content from S3: s3://${s3_bucket}/${s3_key}`);
    } catch (s3Error) {
      logger.error(`Failed to read from S3: ${s3Error.message}`);
      throw new Error(`Failed to read HTML file from S3: ${s3Error.message}`);
    }

    const result = await processHtmlContent(htmlContent);
      
    if (result.success) {
      const processingMethod = result.fallback ? 'fallback text extraction' : 'Mozilla Readability';
      logger.info(`Successfully processed HTML content from s3://${s3_bucket}/${s3_key} using ${processingMethod}`);
      
      return {
        statusCode: 200,
        body: JSON.stringify({
          message: 'Successfully processed HTML content',
          processingMethod: processingMethod,
          title: result.title,
          content: result.content,
          textContent: result.textContent,
          excerpt: result.excerpt,
          metadata: {
            byline: result.byline,
            siteName: result.siteName,
            length: result.length,
            dir: result.dir,
            fallbackUsed: result.fallback || false
          }
        })
      };
    } else {
      logger.error(`Failed to process HTML content: ${result.error}`);
      return {
        statusCode: 500,
        body: JSON.stringify({
          message: 'Failed to process HTML content',
          error: result.error,
          stack: result.stack
        })
      };
    }
  
  } catch (error) {
    logger.error(`Error in lambda handler: ${error.message}`);
    return {
      statusCode: 500,
      body: JSON.stringify({
        message: 'Error processing request',
        error: error.message
      })
    };
  }
};

// // Test function
// async function test() {
//   const event = {
//     "s3_bucket": "insights-jt-sourcebucketddd2130a-nlzn85nayvs6",
//     "s3_key": "fashionbombdaily.com/21f7c4ed87d6/article.html"
//   };
//
//   const result = await exports.handler(event, {});
//   console.log(JSON.stringify(result, null, 2));
// }
//
// // Uncomment to run test
// test();
