const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const webpack = require('webpack');
const TsconfigPathsPlugin = require('tsconfig-paths-webpack-plugin');

module.exports = (env, argv) => {
  const isProduction = argv.mode === 'production';
  
  return {
    mode: argv.mode || 'development',
    entry: './src/index.tsx',
    output: {
      path: path.resolve(__dirname, 'build'),
      filename: isProduction ? '[name].[contenthash].js' : 'bundle.js',
      publicPath: '/',
      clean: true,
    },
    resolve: {
      extensions: ['.tsx', '.ts', '.js'],
      alias: {
        '@': path.resolve(__dirname, 'src'),
        '@/lib/utils': path.resolve(__dirname, 'src/lib/utils'),
      },
      plugins: [
        new TsconfigPathsPlugin({
          configFile: path.resolve(__dirname, 'tsconfig.json'),
        }),
      ],
      modules: [path.resolve(__dirname, 'node_modules'), 'node_modules'],
      fallback: {
        path: false,
        fs: false,
      },
    },
    module: {
      rules: [
        {
          test: /\.(ts|tsx)$/,
          exclude: /node_modules/,
          use: {
            loader: 'ts-loader',
            options: {
              transpileOnly: false,
              configFile: path.resolve(__dirname, 'tsconfig.json'),
            },
          },
        },
        {
          test: /\.css$/,
          use: ['style-loader', 'css-loader', 'postcss-loader'],
        },
      ],
    },
    plugins: [
      new HtmlWebpackPlugin({
        template: path.resolve(__dirname, 'public/index.html'),
      }),
      new webpack.DefinePlugin({
        'process.env': {
          'REACT_APP_API_URL': JSON.stringify(process.env.REACT_APP_API_URL || '/api'),
          'REACT_APP_WEBSOCKET_URL': JSON.stringify(process.env.REACT_APP_WEBSOCKET_URL || ''),
          'REACT_APP_SHOPIFY_SHOP_URL': JSON.stringify('e19833-4.myshopify.com'),
          'SHOPIFY_SHOP_URL': JSON.stringify('e19833-4.myshopify.com'),
        },
      }),
    ],
    devServer: {
      port: 3055,
      hot: true,
      open: true,
      historyApiFallback: true,
      static: {
        directory: path.join(__dirname, 'public'),
        publicPath: '/',
      },
      proxy: [
        {
          context: ['/api'],
          target: 'http://localhost:3560',
          changeOrigin: false,  // Keep original origin for CORS
          secure: false,
          logLevel: 'debug',
          onProxyReq: function(proxyReq, req, res) {
            proxyReq.setHeader('Origin', 'http://localhost:3055');
          },
        }
      ],
    },
  };
};