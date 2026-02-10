#  Copyright (c) 2025. Amazon.com and its affiliates; all rights reserved.
#    This file is Amazon Web Services Content and may not be duplicated or distributed without permission.
EXTRACTION_PROMPT_CAR = """Given the automotive news webpage, first identify and extract ONLY the main article content HTML. Then analyze this content to extract structured information.

Step 1: Identify and extract the main content HTML by:
- Looking for content wrapper elements (typically with classes/IDs like "article", "content", "main", "story")
- Focusing on sections containing substantive paragraphs of text
- Including the headline, byline, publication date, and article body
- Excluding navigation menus, advertisements, sidebars, footers, relative news, and comment sections

Step 2: From the extracted main content, extract the following information:

- Title: Extract the exact headline of the news article (typically the largest text at the top)
- Publication Date: Format as YYYY-MM-DD if available (usually near the headline or author byline)
- Industry: "car",
- Source: Identify the publishing website or organization (the primary domain or explicitly stated news source)
- Summary: Write a journalistic lead paragraph (150-200 characters) that directly summarizes the news without phrases like "this article discusses" or "the report details." Begin with the key innovation, company, or technology advancement as if writing the opening of a news story.
- Keywords: Extract 3-5 technical terms from the body content that would be useful for categorizing this content in an automotive database
- Technical Focus: Based on the article's main thesis, select ONE most applicable category: "automation and robotics", "sustainability", "digital manufacturing", "materials innovation", "safety systems"
- Development Stage: From the main content, identify whether this is "concept", "prototype", "testing", "production-ready", or "in market"
- Content Type: Classify the main article as "case study", "product announcement", "technical analysis", "design concept", "industry trend", or "regulatory update"
- Application Areas: From the technical details in the main text, identify the primary vehicle systems affected (Body, Chassis, Powertrain, Interior, Electronics, etc.)
- Manufacturing Process: From the technical specifications, identify the primary production technique involved
- Company: List the main organization(s) developing or implementing the technology as mentioned in the article body
- Market Impact: Based on expert quotes or analysis in the main text, provide a brief assessment of potential industry significance (high/medium/low)
- Timeline: Expected implementation timeframe if mentioned in the article body or executive statements
- MainContentHTML: The cleaned HTML of just the main article content, remember to include the images in the main content

Your response must be formatted as a valid JSON object with these fields.

Example JSON output:
{
  "title": "BMW Unveils Carbon-Neutral Manufacturing Process for EV Battery Casings",
  "publicationDate": "2025-03-15",
  "industry": "car", 
  "source": "AutomotiveTech Weekly",
  "summary": "BMW has developed a groundbreaking carbon-neutral manufacturing process for EV battery casings that reduces production emissions by 80% while maintaining structural integrity and using recycled materials.",
  "keywords": ["carbon-neutral manufacturing", "battery casings", "recycled aluminum", "emission reduction", "electric vehicles"],
  "technicalFocus": "sustainability",
  "developmentStage": "production-ready",
  "contentType": "technical analysis",
  "applicationAreas": "Powertrain",
  "manufacturingProcess": "Low-Pressure Die Casting",
  "company": "BMW Group",
  "marketImpact": "high",
  "timeline": "Q3 2025 implementation across European facilities",
  "mainContentHTML": "<article class='news-content'><h1>BMW Unveils Carbon-Neutral Manufacturing Process for EV Battery Casings</h1><div class='byline'>By Jane Smith | March 15, 2025</div><p>BMW has announced a breakthrough in sustainable manufacturing with its new carbon-neutral process for producing electric vehicle battery casings...</p><p>The innovative technique utilizes 100% recycled aluminum and is powered entirely by renewable energy sources...</p><!-- Additional paragraphs of main content --></article>"
}

If any field cannot be determined from the main article content with reasonable confidence, use "" as the value.
"""


EXTRACTION_PROMPT_FASHION = """Given the fashion industry news webpage, first identify and extract ONLY the main article content HTML. Then analyze this content to extract structured information about fashion trends, brand performance, and industry insights.

Step 1: Identify and extract the main content HTML by:
- Looking for content wrapper elements (typically with classes/IDs like "article", "content", "post-body", "story")
- Focusing on sections containing substantive paragraphs of text about fashion industry analysis
- Including the headline, author information, publication date, and article body
- Excluding navigation menus, advertisements, subscription prompts, sidebars, footers, and related article links

Step 2: From the extracted main content, extract the following information:

- Title: Extract the exact headline of the fashion article
- Publication Date: Format as YYYY-MM-DD if available
- Industry: "fashion"
- Source: Identify the publishing website or organization (e.g., Business of Fashion, Vogue Business)
- Authors: List the article authors and their roles if mentioned
- Summary: Write a journalistic lead paragraph (200-350 characters) that concisely captures the main insight or data point from the article without phrases like "this article discusses"
- Keywords: Extract 3-5 key terms relevant to fashion industry analysis (brands, metrics, events, trends)
- Article Type: Select ONE most applicable category: "trend analysis", "brand performance", "market report", "fashion week coverage", "consumer insights", "executive interview", "industry data"
- Featured Brands: List the primary fashion brands mentioned in order of prominence
- Industry Segment: Identify the primary segment(s) covered: "luxury", "fast fashion", "streetwear", "accessories", "beauty", "retail", "e-commerce"
- Key Metrics: Extract any quantitative data points mentioned (market share, growth percentages, sales figures)
- Social Platforms: Identify which social media platforms are discussed (Instagram, TikTok, Twitter, etc.)
- Geographic Focus: Extract regions or markets specifically analyzed (e.g., "global", "European market", "China")
- Industry Figures: List notable fashion executives, designers, or celebrities mentioned
- Data Sources: Identify the origin of any data or research cited in the article
- MainContentHTML: The cleaned HTML of just the main article content, remember to include the images in the main content

Your response must be formatted as a valid JSON object with these fields.

Example JSON output:
{
  "title": "5 Brands That Dominated the Social Conversation During Milan Fashion Week",
  "publicationDate": "2025-03-11",
  "industry": "fashion",
  "source": "Business of Fashion",
  "authors": ["Imran Amed", "Amanda Dargan", "Hannah Crump"],
  "summary": "DSquared2's 30th anniversary show led social media conversations during Milan Fashion Week AW25, followed by Moschino and Versace, while Prada and Gucci received less user-generated content attention.",
  "keywords": ["fashion week", "social media analytics", "user-generated content", "brand performance", "cultural impact"],
  "articleType": "brand performance",
  "featuredBrands": ["DSquared2", "Moschino", "Versace", "Antonio Marras", "Fendi", "Gucci", "Prada"],
  "industrySegment": "luxury",
  "keyMetrics": "DSquared2 share of voice:10.9%, Moschino share of voice:7.9%, Versace share of voice:7.8%",
  "socialPlatforms": ["Instagram", "TikTok"],
  "geographicFocus": "global",
  "industryFigures": ["Dean and Dan Caten", "Donatella Versace", "Silvia Venturini Fendi", "Naomi Campbell", "Doechii"],
  "dataSources": "BoF INSIGHTS PULSE powered by Quilt.AI",
  "mainContentHTML": "<article class='article-content'><h1>5 Brands That Dominated the Social Conversation During Milan Fashion Week</h1><div class='byline'>By Imran Amed, Amanda Dargan, Hannah Crump | 11 March 2025</div><p>DSquared2, Moschino and Versace led the user-generated conversation on social media during Milan Fashion Week according to BoF Insights' new social intelligence tool PULSE, powered by Quilt.AI.</p><!-- Additional paragraphs of main content --></article>"
}

If any field cannot be determined from the main article content with reasonable confidence, use "unknown" as the value.
"""


EXTRACTION_PROMPT_FURNITURE = """Given the design/furniture news webpage, first identify and extract ONLY the main article content HTML. Then analyze this content to extract structured information.

Step 1: Identify and extract the main content HTML by:
- Looking for content wrapper elements (typically with classes/IDs like "article", "content", "story", "post")
- Focusing on sections containing substantive paragraphs of text about the design
- Including the headline, designer/brand information, publication date, and article body
- Excluding navigation menus, advertisements, sidebars, footers, and comment sections

Step 2: From the extracted main content, extract the following information:

- Title: Extract the exact headline of the design article
- Publication Date: Format as YYYY-MM-DD if available
- Industry: "furniture"
- Source: Identify the publishing website or organization
- Summary: Write a journalistic lead paragraph (150-200 characters) that directly summarizes the design news without phrases like "this article discusses." Begin with the key design innovation, collection name, or designer as if writing the opening of a design magazine feature.
- Keywords: Extract 3-5 key terms from the body content (materials, design movements, techniques, designers, brands)
- Design Focus: Select ONE most applicable category: "sustainability", "innovative materials", "modular design", "minimalism", "biophilic design", "luxury", "multifunctional", "artisanal craftsmanship"
- Development Stage: Identify whether this is "concept", "prototype", "limited edition", "new collection", or "established product line"
- Content Type: Classify as "product launch", "designer profile", "collection showcase", "design analysis", "trend report", or "exhibition coverage"
- Application Areas: Identify the primary spaces for the design (Indoor Living, Outdoor Spaces, Kitchen, Bathroom, Office, Hospitality, Public Spaces, etc.)
- Materials: Identify the primary materials mentioned (wood, metal, textile, ceramic, glass, plastic, composite, etc.)
- Brand/Designer: List the main brand(s) and designer(s) featured in the article
- Target Market: Based on context, identify "luxury", "mid-range", "accessible", or "contract/commercial"
- Design Aesthetic: Identify key aesthetic terms (e.g., "minimalist", "organic", "industrial", "scandinavian", "art deco")
- MainContentHTML: The cleaned HTML of just the main article content, remember to include the images in the main content

Your response must be formatted as a valid JSON object with these fields.

Example JSON output:
{
  "title": "Vondom Introduces Pasadena Collection by Jean-Marie Massaud",
  "publicationDate": "2025-05-22",
  "industry": "furniture",
  "source": "Architonic",
  "summary": "Jean-Marie Massaud's new Pasadena Collection for Vondom reimagines outdoor living with architectural proportions and exceptional comfort, featuring modular sofas, lounge chairs, side tables and sun loungers.",
  "keywords": ["outdoor furniture", "Jean-Marie Massaud", "modular design", "architectural proportions", "weather-resistant materials"],
  "designFocus": "modular design",
  "developmentStage": "new collection",
  "contentType": "collection showcase",
  "applicationAreas": "Outdoor Spaces",
  "materials": "aluminum, quick-dry upholstery",
  "brandDesigner": "Vondom, Jean-Marie Massaud",
  "targetMarket": "luxury",
  "designAesthetic": "contemporary minimalist",
  "mainContentHTML": "<article class='story'><h1>Adapting timeless comfort for outdoor living</h1><div class='byline'>Text by Vondom | 22.05.25</div><p>A collection that captures the essence of outdoor living, combining refined lines and generous comfort in a timeless design.</p><p>The Pasadena Collection, designed by Jean-Marie Massaud for Vondom, is a celebration of balance, comfort and refined aesthetics...</p><!-- Additional paragraphs of main content --></article>"
}

If any field cannot be determined from the main article content with reasonable confidence, use "unknown" as the value.
"""

# Default prompt for general e-commerce product analysis
DEFAULT_PROMPT = """
You are a website trend analysis engineer specializing in analyzing single product pages on e-commerce platforms such as 1688, Taobao, and Amazon.com. Based on the visible webpage content, please conduct a structured and in-depth analysis of the product, focusing on the following dimensions:

1. Basic Product Information: 
    Product name and model
    Core functions and main uses
    Materials and technical specifications
    Product images and detailed descriptions

2. Target Users and Application Scenarios: 
    Infer the main consumer groups (e.g., laboratories, factories, households) based on product descriptions and images
    Typical application scenarios and usage frequency

3. Product Dependencies and Complementary Needs
    Determine whether the product is used independently or requires other products/accessories/consumables
    List possible essential accessories, recommended complementary products, or common combinations
    Check if the webpage includes "recommended pairings", "bundle offers", or "related accessories" prompts

4. Pricing and Competitive Landscape
    Record the single item price and total sales volume displayed on the page
    If there are "similar recommendations" or "related products" sections, compare prices and functions to infer market competition
    Identify price differentiation factors compared to similar products (e.g., premium materials, advanced features, larger capacity, better performance)

5. Product Innovation and Differentiation
    Note if the product description emphasizes new materials, new designs, or new features
    Identify differentiation highlights compared to similar products on the page
    Look for terms like "patent" or "exclusive technology"

6. Durability and Environmental Attributes
    Assess product durability and provide an estimation of how long the product can be used (e.g., "5-7 years", "10,000 operation cycles", "3-5 years of daily use")
    Check if environmentally friendly materials, processes, standards or certifications are used

7. Market Opportunities and Risks (Estimation)
    Based on product features and application scenarios, speculate potential emerging markets or niche demands
    Look for policy or standard hints like "environmental protection," "compliance," or "new national standards"

8. Supply Chain and Inventory
    Check if the webpage shows inventory quantity
    Note tags like in-stock, pre-sale, or custom order
    Assess supply stability and logistics timeliness

Make full use of all visible webpage information (images, descriptions, reviews, recommendations, etc.) and combine reasoning and comparison to fill in missing market data. Emphasize analysis of the target market and its characteristics. Produce structured and comparable analytical conclusions to facilitate subsequent data supplementation and decision-making.

MANDATORY OUTPUT FORMAT: You MUST respond with ONLY a valid JSON object. No additional text, explanations, or markdown formatting is allowed.

REQUIRED JSON STRUCTURE:
{
    "title": "产品的主要标题/名称",
    "summary": "对产品分析的简明总结，涵盖上述所有8个维度（控制在100字以内）。必须包括对影响价格的因素分析，如规格、材料、功能或其他参数，影响产品定价结构的内容。",
    "Basic Product Information": {
        "coreFunctions": "主要功能/用途",
        "materialsSpecs": "材料和规格",
        "imagesDescriptions": "产品图片和详细描述"
    },
    "Target Users and Application Scenarios": {
        "mainConsumers": "主要消费群体",
        "applicationScenarios": "典型场景/使用频率"
    },
    "Pricing and Competitive Landscape": {
        "price": "单件价格",
        "salesVolume": "展示销量",
        "competitionSection": "与同类产品对比",
        "priceDifferentiators": ["因素1", "因素2"]
    },
    "Product Innovation and Differentiation": {
        "innovations": "创新功能/材料/设计",
        "differentiation": "差异化亮点",
        "patentOrExclusive": "专利/独家技术存在"
    },
    "Durability and Environmental Attributes": {
        "durability": "预计寿命或使用时间（例如，“5-7年”，“10000次操作周期”）",
        "environmentalInfo": "环保材料、工艺、标准和认证"
    },
    "User Concerns and Feedback": {
        "userConcerns": "用户对产品各方面（功能、质量、耐用性、易用性等）的意见、关切和反馈",
        "commonIssues": "用户频繁提及的问题或故障",
        "positiveHighlights": "用户评价中常提及的积极方面"
    },
    "Product Dependencies and Complementary Needs": {
        "independentUsage": true,
        "essentialAccessories": ["配件1", "配件2"],
        "recommendedComplements": ["搭配品1", "搭配品2"],
        "relatedPrompts": "捆绑优惠/相关配件信息"
    },
    "Market Opportunities and Risks": {
        "opportunities": "潜在新市场",
        "risks": "风险/政策标准"
    },
    "Supply Chain and Inventory": {
        "inventory": "库存数量/备货信息",
        "supplyStability": "稳定性/物流说明"
    },
    "keywords": ["最多", "10个", "相关", "产品", "关键词"],
    "mainContentHTML": "The main product content in clean HTML format, excluding navigation, ads, etc."
}


EXAMPLE OUTPUT FORMAT:
{
    "title": "数字磁力搅拌加热板实验室设备",
    "summary": "实验室级磁力搅拌加热板，配备最高300°C的数字温控和可变搅拌速度，适用于研究实验室和教育机构。用于化学合成和样品准备。价格受温度范围（300°C与200°C型号）、加热板材质（陶瓷与铝）及认证（CE/FDA增加15-20%成本）影响。带可编程设置的高端型号价格高出40-60%。需要磁力搅拌棒和玻璃器皿配件。",
    "Basic Product Information": {
        "name": "数字磁力搅拌加热板 MS-300D",
        "coreFunctions": "用于加热并搅拌液体样品，速度和温度可调，适用于化学和生物实验室。",
        "materialsSpecs": "陶瓷涂层加热板，不锈钢机身，数字LCD控制，温度范围25–300°C，搅拌速度100–1500转/分。"
    },
    "Target Users and Application Scenarios": {
        "mainConsumers": "科学实验室、教育机构、研究设施",
        "applicationScenarios": "化学合成、样品加热、滴定、常规混合；日常至密集的学术或工业实验室使用"
    },
    "Pricing and Competitive Landscape": {
        "price": "179美元",
        "salesVolume": "过去一个月销量262台",
        "competitionSection": "类似型号价格区间120–220美元；经济型无数字显示，高端型号提供更大加热板或远程App控制。",
        "priceDifferentiators": ["陶瓷加热板", "数字LCD", "CE/FDA认证", "可编程计时器"]
    },
    "Product Innovation and Differentiation": {
        "innovations": "触摸屏数字界面，自动断电功能",
        "differentiation": "温度范围更广，控制更精准，优于大多数入门级型号",
        "patentOrExclusive": "无专利声明；提及独家数字校准模式"
    },
    "Durability and Environmental Attributes": {
        "durability": "正常实验室使用预计寿命5-7年。额定操作次数>20000次，陶瓷加热板抗刮擦及耐化学性能强",
        "environmentalInfo": "符合RoHS标准组件，低能耗操作，可回收包装。列有CE、RoHS认证。"
    },
    "User Concerns and Feedback": {
        "userConcerns": "用户提及长期使用后插头耐用性问题。一些用户反馈温度校准存在困难。",
        "commonIssues": "约8%的评论指出偶发温度波动，多位用户认为电源线长度过短。",
        "positiveHighlights": "因耐化学性、温度控制精确和运行安静而备受好评。"
    },
    "Product Dependencies and Complementary Needs": {
        "independentUsage": false,
        "essentialAccessories": ["磁力搅拌棒", "烧杯", "温度探头"],
        "recommendedComplements": ["实验室玻璃器皿", "加热板保护盖"],
        "relatedPrompts": "产品页面显示“经常一起购买：搅拌棒，玻璃器皿套装”"
    },
    "Market Opportunities and Risks": {
        "opportunities": "教育STEM实验室和小规模生物技术初创企业需求增长",
        "risks": "价格敏感市场，新安全合规法规可能影响欧盟市场准入"
    },
    "Supply Chain and Inventory": {
        "inventory": "库存120台；每隔两周补货一次",
        "supplyStability": "稳定；多家供应商，优先国际空运配送"
    },
    "keywords": ["磁力搅拌器", "加热板", "实验室设备", "数字控制", "温度控制", "科学仪器", "化学合成", "样品准备"],
    "mainContentHTML": "<div class='product-info'><h1>Digital Magnetic Stirrer Hot Plate</h1><p>Professional laboratory equipment with precise heating and stirring capabilities...</p></div>"
}


CRITICAL FORMATTING REQUIREMENTS:
1. Your response must start with { and end with }
2. All string values must be properly escaped (use \\\" for quotes, \\n for newlines)
3. The summary must cover all 8 analysis dimensions in a concise format (maximum 100 words)
4. The summary must specifically analyze what specifications, parameters, or factors influence the product's pricing
5. Keywords must be an array of maximum 10 relevant terms, not a single string
6. mainContentHTML must contain valid HTML without navigation or ads
7. Do not include any text before or after the JSON object
8. Do not wrap the JSON in code blocks or markdown
9. Ensure the JSON is valid and parseable
10. No matter what the input language is, the output must be in Chinese, generate the JSON value in Chinese. Be sure to translate the output title into Chinese.
11. Display N/A if there's no information for the required information and output.

FINAL REMINDER: Your entire response must be the JSON object and absolutely nothing else. Any deviation from this format will be considered an error. Do not add explanations, do not add markdown formatting, do not add any text outside the JSON structure.

START YOUR RESPONSE WITH: {
END YOUR RESPONSE WITH: }
"""

url_prompt_matching = {
    "https://www.businessoffashion.com": EXTRACTION_PROMPT_FASHION,
    "https://www.architonic.com": EXTRACTION_PROMPT_FURNITURE,
    "https://www.autonews.com": EXTRACTION_PROMPT_CAR,
    "https://fashionbombdaily.com" : EXTRACTION_PROMPT_FASHION,
    "https://www.thewesternoutfitters.com": EXTRACTION_PROMPT_FASHION,
}

# Add a new section for user concerns and feedback
def add_user_concerns_section():
    """
    This function is a placeholder to document the addition of the User Concerns and Feedback section.
    The section has been added to the DEFAULT_PROMPT to capture comprehensive user feedback
    about all aspects of the product, not just durability and environmental attributes.
    """
    pass