module.exports = {
    "roots": [
        "src"
    ],
    "transform": {
        "^.+\\.ts$": ["ts-jest", { tsconfig: "tsconfig.test.json" }]
    },
}; 
